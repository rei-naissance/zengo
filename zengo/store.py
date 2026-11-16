"""User config (JSON) + history and saved words (SQLite), kept in %APPDATA%\\Zengo."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

from .ai import DEFAULT_MODEL

APP_DIR = Path(os.getenv("APPDATA") or Path.home()) / "Zengo"

DEFAULTS = {
    "deepl_key": "",
    "ollama_key": "",
    "ollama_model": DEFAULT_MODEL,
    "en_variant": "EN-US",          # EN-US | EN-GB
    "ja_formality": "default",      # default | prefer_more | prefer_less
    "double_copy_ms": 500,
    "hotkey_enabled": True,
    "furigana": True,
    "popup_pinned": False,
    "auto_explain": False,          # run the AI explanation automatically in the popup
    "theme": "system",              # system | light | dark
    "history_enabled": True,
}


class Config:
    def __init__(self, path: Path = APP_DIR / "config.json"):
        self.path = path
        self._lock = threading.Lock()
        self.data = dict(DEFAULTS)
        if path.exists():
            try:
                self.data.update(json.loads(path.read_text(encoding="utf-8")))
            except ValueError:
                pass
        # keys missing from Settings fall back to the project .env
        changed = not path.exists()
        for k, env in (("deepl_key", "DEEPL_API_KEY"), ("ollama_key", "OLLAMA_API_KEY")):
            if not self.data[k] and os.getenv(env):
                self.data[k] = os.getenv(env).strip()
                changed = True
        if changed:
            self.save()

    def __getitem__(self, k):
        return self.data.get(k, DEFAULTS.get(k))

    def update(self, values: dict) -> None:
        with self._lock:
            for k, v in values.items():
                if k in DEFAULTS:
                    self.data[k] = type(DEFAULTS[k])(v) if DEFAULTS[k] is not None else v
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")


class UserData:
    def __init__(self, path: Path = APP_DIR / "user.db"):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._con.executescript("""
            CREATE TABLE IF NOT EXISTS history(
                id INTEGER PRIMARY KEY, text TEXT UNIQUE, translation TEXT, ja INTEGER, ts REAL);
            CREATE TABLE IF NOT EXISTS saved(
                id INTEGER PRIMARY KEY, word TEXT UNIQUE, reading TEXT, base TEXT,
                meaning TEXT, pos TEXT, sentence TEXT, segs TEXT, ts REAL);
        """)

    def _q(self, sql: str, args=()) -> list[dict]:
        with self._lock:
            cur = self._con.execute(sql, args)
            cols = [c[0] for c in cur.description] if cur.description else []
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            self._con.commit()
            return rows

    # history
    def add_history(self, text: str, translation: str, ja: bool) -> None:
        self._q("INSERT INTO history(text, translation, ja, ts) VALUES(?,?,?,?) "
                "ON CONFLICT(text) DO UPDATE SET translation=excluded.translation, ts=excluded.ts",
                (text, translation, int(ja), time.time()))

    def history(self, query: str = "", limit: int = 300) -> list[dict]:
        like = f"%{query}%"
        return self._q("SELECT * FROM history WHERE text LIKE ? OR translation LIKE ? "
                       "ORDER BY ts DESC LIMIT ?", (like, like, limit))

    def delete_history(self, hid: int) -> None:
        self._q("DELETE FROM history WHERE id=?", (hid,))

    def clear_history(self) -> None:
        self._q("DELETE FROM history")

    # saved words
    def save_word(self, w: dict) -> None:
        self._q("INSERT OR REPLACE INTO saved(word, reading, base, meaning, pos, sentence, segs, ts) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (w["word"], w.get("reading", ""), w.get("base", ""), w.get("meaning", ""),
                 w.get("pos", ""), w.get("sentence", ""), json.dumps(w.get("segs", []), ensure_ascii=False),
                 time.time()))

    def unsave_word(self, word: str) -> None:
        self._q("DELETE FROM saved WHERE word=?", (word,))

    def saved(self, query: str = "") -> list[dict]:
        like = f"%{query}%"
        rows = self._q("SELECT * FROM saved WHERE word LIKE ? OR meaning LIKE ? OR reading LIKE ? "
                       "ORDER BY ts DESC", (like, like, like))
        for r in rows:
            r["segs"] = json.loads(r["segs"] or "[]")
        return rows

    def saved_words(self) -> set[str]:
        return {r["word"] for r in self._q("SELECT word FROM saved")}
