"""Zengo desktop app: main window + Ctrl+C-twice popup + tray, on the system WebView2."""
from __future__ import annotations

import csv
import json
import sys
import threading
import time
from pathlib import Path

import webview
from dotenv import load_dotenv

from . import win
from .ai import AIError, OllamaClient, explain_messages
from .analyze import Analyzer, is_japanese, ruby
from .dictionary import Dictionary
from .hotkey import DoubleCopyListener
from .store import Config, UserData
from .translate import Translator

ROOT = Path(__file__).resolve().parent.parent
UI = Path(__file__).resolve().parent / "ui"
POPUP_TITLE = "Zengo Popup"
MAX_CHARS = 3000


class Api:
    """Everything here is callable from JS as window.pywebview.api.<name>(...).
    pywebview runs each call on its own thread. Keep internals in underscore attrs."""

    def __init__(self, app: "App"):
        self._app = app

    # ---- lookups ----------------------------------------------------------
    def analyze(self, text: str) -> dict:
        text = (text or "")[:MAX_CHARS]
        ja = is_japanese(text)
        return {"ja": ja, "analysis": self._app.analyzer.analyze(text) if ja else None}

    def translate(self, text: str, record: bool = True) -> dict:
        a = self._app
        text = (text or "").strip()[:MAX_CHARS]
        if not text:
            return {"error": "Nothing to translate."}
        try:
            r = dict(a.translator.translate(text))
        except Exception as e:  # auth, quota, network
            return {"error": f"Translation failed: {e}"}
        if r["target"] == "JA":
            r["analysis"] = a.analyzer.analyze(r["text"])
        if record and a.config["history_enabled"]:
            a.user.add_history(text, r["text"], r["source"] == "JA")
        return r

    # ---- AI ---------------------------------------------------------------
    def explain(self, win_name: str, rid: int, text: str, translation: str | None, detail: str = "brief"):
        ja = is_japanese(text)
        analysis = self._app.analyzer.analyze(text) if ja else (
            self._app.analyzer.analyze(translation) if translation else None)
        msgs = explain_messages(text, translation, ja, analysis, detail)
        self._app.start_stream(win_name, rid, msgs)

    def ask(self, win_name: str, rid: int, question: str):
        conv = self._app.conversations.get(win_name)
        if not conv:
            raise ValueError("Run an explanation first.")
        self._app.start_stream(win_name, rid, conv + [{"role": "user", "content": question}])

    def cancel_ai(self, win_name: str):
        self._app.ai_current[win_name] = None

    # ---- history / saved ----------------------------------------------------
    def history_list(self, query: str = ""):
        return self._app.user.history(query)

    def history_delete(self, hid: int):
        self._app.user.delete_history(hid)

    def history_clear(self):
        self._app.user.clear_history()

    def saved_list(self, query: str = ""):
        return self._app.user.saved(query)

    def saved_set(self):
        return sorted(self._app.user.saved_words())

    def save_word(self, w: dict):
        w = dict(w)
        w["segs"] = ruby(w["word"], w.get("reading"))
        self._app.user.save_word(w)
        self._app.broadcast("zengo.onSavedChanged()")

    def unsave_word(self, word: str):
        self._app.user.unsave_word(word)
        self._app.broadcast("zengo.onSavedChanged()")

    def export_saved(self):
        res = (self._app.main or self._app.popup).create_file_dialog(
            webview.FileDialog.SAVE, save_filename="zengo-words.csv", file_types=("CSV (*.csv)",))
        if not res:
            return None
        path = res if isinstance(res, str) else res[0]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            wr = csv.writer(f)
            wr.writerow(["Word", "Reading", "Meaning", "Part of speech", "Sentence"])
            for r in self._app.user.saved():
                wr.writerow([r["word"], r["reading"], r["meaning"], r["pos"], r["sentence"]])
        return path

    # ---- settings -----------------------------------------------------------
    def settings_get(self):
        c = self._app.config.data
        mask = lambda k: ("…" + k[-4:]) if k else ""
        return {**{k: v for k, v in c.items() if not k.endswith("_key")},
                "deepl_key": mask(c["deepl_key"]), "ollama_key": mask(c["ollama_key"]),
                "has_deepl": bool(c["deepl_key"]), "has_ollama": bool(c["ollama_key"]),
                "autostart": win.get_autostart()}

    def settings_save(self, values: dict):
        values = dict(values)
        if "autostart" in values:
            win.set_autostart(bool(values.pop("autostart")))
        for k in ("deepl_key", "ollama_key"):
            if k in values and (values[k] or "").startswith("…"):
                values.pop(k)  # unchanged masked value
        self._app.config.update(values)
        self._app.apply_config()
        self._app.broadcast(f"zengo.onConfig({json.dumps(self.settings_get())})")
        return self.settings_get()

    def deepl_usage(self):
        try:
            return self._app.translator.usage()
        except Exception as e:
            return {"error": str(e)}

    def ollama_models(self):
        try:
            return {"models": OllamaClient(self._app.config["ollama_key"]).models()}
        except AIError as e:
            return {"error": str(e)}

    # ---- windows ------------------------------------------------------------
    def popup_hide(self):
        self._app.hide_popup()

    def popup_blur(self):
        if not self._app.config["popup_pinned"] and time.monotonic() - self._app.popup_shown_at > 0.4:
            self._app.hide_popup()

    def set_pref(self, key: str, value):
        if key in ("furigana", "popup_pinned", "auto_explain"):
            self._app.config.update({key: value})

    def open_in_app(self, text: str, view: str | None = None):
        self._app.hide_popup()
        self._app.show_main(text, view)

    def open_url(self, url: str):
        if url.startswith("https://jisho.org/"):
            import webbrowser
            webbrowser.open(url)


class App:
    def __init__(self, start_hidden: bool):
        self.config = Config()
        self.user = UserData()
        self.dictionary = Dictionary()
        self.analyzer = Analyzer(self.dictionary)
        self.translator = Translator(self.config)
        self.api = Api(self)
        self.conversations: dict[str, list] = {}
        self.ai_current: dict[str, int | None] = {}
        self.popup_visible = False
        self.popup_shown_at = 0.0
        self.quitting = False
        self._popup_hwnd = 0
        self._popup_loaded = threading.Event()

        self.main = None  # created on demand and destroyed on close, to stay light in the tray
        self._main_loaded = threading.Event()
        self._main_lock = threading.Lock()
        self.popup = webview.create_window(
            POPUP_TITLE, url=str(UI / "popup.html"), js_api=self.api, width=520, height=620,
            frameless=True, easy_drag=False, on_top=True, hidden=True, background_color=self._bg(),
            text_select=True, resizable=True, min_size=(360, 260))
        self.popup.events.loaded += self._popup_loaded.set
        if not start_hidden:
            self._create_main()

        self.hotkey = DoubleCopyListener(self._on_double_copy, self.config["double_copy_ms"])
        self.hotkey.start()
        self._start_tray()

    # ---- config / theme -----------------------------------------------------
    def _bg(self) -> str:
        return "#1b1a18" if self._is_dark() else "#fbfaf7"

    def _is_dark(self) -> bool:
        t = self.config["theme"]
        return win.system_dark_mode() if t == "system" else t == "dark"

    def _style(self, title: str, rounded: bool):
        hwnd = win.find_window(title)
        if hwnd:
            win.style_window(hwnd, self._is_dark(), rounded)

    def apply_config(self):
        self.hotkey.window = self.config["double_copy_ms"] / 1000
        self._style("Zengo", rounded=False)
        self._style(POPUP_TITLE, rounded=True)

    def broadcast(self, js: str):
        for w in (self.main, self.popup):
            if w is None:
                continue
            try:
                w.evaluate_js(js)
            except Exception:
                pass

    # ---- popup --------------------------------------------------------------
    def _on_double_copy(self):
        if not self.config["hotkey_enabled"]:
            return
        threading.Thread(target=self._popup_from_clipboard, daemon=True).start()

    def _popup_from_clipboard(self):
        time.sleep(0.12)  # let the source app finish writing the clipboard
        text = win.get_clipboard_text().strip()
        if text:
            self.show_popup(text[:MAX_CHARS])

    def show_popup(self, text: str):
        self._popup_loaded.wait(10)
        hwnd = self._popup_hwnd or win.find_window(POPUP_TITLE)
        self._popup_hwnd = hwnd
        if hwnd and not self.popup_visible:
            cx, cy = win.cursor_pos()
            left, top, right, bottom = win.work_area_at(cx, cy)
            x0, y0, x1, y1 = win.window_rect(hwnd)
            w, h = x1 - x0, y1 - y0
            x = min(max(cx + 12, left), right - w)
            y = cy + 18 if cy + 18 + h <= bottom else max(top, cy - h - 12)
            win.place_window(hwnd, x, y)
        self.popup_shown_at = time.monotonic()
        self.popup.show()
        self.popup_visible = True
        if hwnd:
            win.style_window(hwnd, self._is_dark(), rounded=True)
            win.force_foreground(hwnd)
        self.popup.evaluate_js(f"zengo.show({json.dumps({'text': text}, ensure_ascii=False)})")

    def hide_popup(self):
        if self.popup_visible:
            self.popup_visible = False
            self.ai_current["popup"] = None
            self.popup.hide()

    # ---- main window ----------------------------------------------------------
    def _create_main(self):
        self._main_loaded.clear()
        w = webview.create_window(
            "Zengo", url=str(UI / "index.html"), js_api=self.api, width=1120, height=760,
            min_size=(760, 520), background_color=self._bg(), text_select=True)
        w.events.loaded += self._main_loaded.set
        w.events.shown += lambda: self._style("Zengo", rounded=False)
        w.events.closed += self._on_main_closed
        self.main = w
        return w

    def show_main(self, text: str | None = None, view: str | None = None):
        with self._main_lock:
            if self.main is None:
                self._create_main()
        self._main_loaded.wait(15)
        self.main.show()
        self.main.restore()
        hwnd = win.find_window("Zengo")
        if hwnd:
            win.force_foreground(hwnd)
        if text:
            self.main.evaluate_js(f"zengo.openText({json.dumps(text, ensure_ascii=False)})")
        elif view:
            self.main.evaluate_js(f"zengo.openView({json.dumps(view)})")

    def _on_main_closed(self):
        # Window is gone; the app keeps running in the tray with only the popup alive.
        self.main = None
        self.ai_current["main"] = None
        self.conversations.pop("main", None)

    # ---- AI streaming ---------------------------------------------------------
    def start_stream(self, win_name: str, rid: int, messages: list[dict]):
        self.ai_current[win_name] = rid
        threading.Thread(target=self._stream, args=(win_name, rid, messages), daemon=True).start()

    def _stream(self, win_name: str, rid: int, messages: list[dict]):
        window = self.main if win_name == "main" else self.popup
        if window is None:
            return
        client = OllamaClient(self.config["ollama_key"], self.config["ollama_model"])
        buf, out, last = [], [], [time.monotonic()]
        alive = lambda: self.ai_current.get(win_name) == rid

        def flush():
            if buf and alive():
                s = "".join(buf)
                buf.clear()
                window.evaluate_js(f"zengo.aiChunk({rid}, {json.dumps(s, ensure_ascii=False)})")

        def on_chunk(c: str):
            buf.append(c)
            out.append(c)
            if time.monotonic() - last[0] > 0.05:
                flush()
                last[0] = time.monotonic()

        try:
            client.stream_chat(messages, on_chunk, should_stop=lambda: not alive())
            flush()
            if alive():
                self.conversations[win_name] = messages + [{"role": "assistant", "content": "".join(out)}]
                window.evaluate_js(f"zengo.aiDone({rid})")
        except Exception as e:
            if alive():
                window.evaluate_js(f"zengo.aiError({rid}, {json.dumps(str(e))})")

    # ---- tray -------------------------------------------------------------------
    def _start_tray(self):
        import pystray
        from PIL import Image, ImageDraw

        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((2, 2, 62, 62), 14, fill="#c2410c")
        logo = Image.open(UI / "logo.png").convert("RGBA")
        logo.thumbnail((54, 54), Image.LANCZOS)
        img.alpha_composite(logo, ((64 - logo.width) // 2, (64 - logo.height) // 2))

        def toggle_hotkey(icon, item):
            self.config.update({"hotkey_enabled": not self.config["hotkey_enabled"]})

        def from_clip(icon, item):
            text = win.get_clipboard_text().strip()
            if text:
                self.show_main(text[:MAX_CHARS])

        menu = pystray.Menu(
            pystray.MenuItem("Open Zengo", lambda: self.show_main(), default=True),
            pystray.MenuItem("Translate clipboard", from_clip),
            pystray.MenuItem("Ctrl+C twice enabled", toggle_hotkey,
                             checked=lambda item: self.config["hotkey_enabled"]),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self.quit()),
        )
        self.tray = pystray.Icon("zengo", img, "Zengo: select text, press Ctrl+C twice", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    def quit(self):
        self.quitting = True
        self.hotkey.stop()
        self.tray.stop()
        for w in (self.popup, self.main):
            if w is None:
                continue
            try:
                w.destroy()
            except Exception:
                pass


def main():
    load_dotenv(ROOT / ".env")
    app = App(start_hidden="--tray" in sys.argv)
    if "--demo" in sys.argv:
        import os
        text = os.getenv("ZENGO_DEMO_TEXT", "昨日、友達に日本語の本を読ませられたんですけど、全然分からなかった。")
        target = os.getenv("ZENGO_DEMO_TARGET", "popup")

        def demo():
            time.sleep(2)
            if target == "popup":
                app.config.data["popup_pinned"] = True
                app.show_popup(text)
            else:
                app.show_main(text)
            if "--shot" in sys.argv:  # dev: screen-grab the window, then quit
                from PIL import ImageGrab
                time.sleep(float(os.getenv("ZENGO_SHOT_DELAY", "3")))
                title = POPUP_TITLE if target == "popup" else "Zengo"
                ImageGrab.grab(bbox=win.window_rect(win.find_window(title)), all_screens=True).save(
                    sys.argv[sys.argv.index("--shot") + 1])
                app.quit()
        threading.Thread(target=demo, daemon=True).start()
    # private_mode: no persistent WebView2 cache, so an updated UI always loads fresh
    webview.start(private_mode=True)
