"""Ollama Cloud (ollama.com) chat client + tutor prompts."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, Iterable

BASE_URL = "https://ollama.com"
DEFAULT_MODEL = "deepseek-v4.1-flash"

SYSTEM = """You are a friendly, precise Japanese tutor for an English-speaking learner \
(roughly JLPT N4-N3). You explain real Japanese the learner copied from the web, games, \
chats or books. Be accurate about grammar and nuance; never invent readings. \
Use Markdown: short headings (###), bullet lists, **bold** for key Japanese terms. \
Always give readings in hiragana in brackets after kanji words you mention, e.g. 先生【せんせい】. \
Do not repeat the whole word-by-word dictionary breakdown: the app already shows it. \
Focus on what a dictionary can't tell them."""


class AIError(Exception):
    pass


def _hint(analysis: dict | None) -> str:
    if not analysis:
        return ""
    rows = []
    for w in analysis["words"]:
        if w["kind"] == "symbol":
            continue
        bits = [w["surface"]]
        if w.get("base") and w["base"] != w["surface"]:
            bits.append(f"base {w['base']}")
        if w.get("parts"):
            bits.append(" + ".join(p["label"] for p in w["parts"]))
        bits.append(w["pos"])
        rows.append(" | ".join(bits))
    return "Tokenizer output (may contain mistakes):\n" + "\n".join(rows[:80])


def explain_messages(text: str, translation: str | None, ja: bool, analysis: dict | None,
                     detail: str = "brief") -> list[dict]:
    length = ("Keep it under ~180 words total: it is shown in a small popup."
              if detail == "brief" else "Be thorough but skimmable (up to ~450 words).")
    if ja:
        task = f"""Explain this Japanese:
「{text}」
Machine translation: {translation or "(unavailable)"}

{_hint(analysis)}

Sections:
### Meaning
A natural English rendering, and a literal one if it differs meaningfully.
### Nuance & tone
Politeness level, who might say this to whom, emotion or implication, what's left unsaid, \
sentence-ending particles. Point out where the machine translation loses or distorts nuance.
### Grammar points
2-4 key patterns used, each with a one-line explanation and one short example sentence.
{length}"""
    else:
        task = f"""The learner wrote this English and wants to say it in Japanese:
"{text}"
Machine translation: {translation or "(unavailable)"}

{_hint(analysis)}

Sections:
### How the translation works
Walk through the Japanese phrase by phrase and explain the choices (word choice, particles, politeness).
### Other ways to say it
A casual version and a polite version (and a very formal one if relevant), each with a one-line note on when to use it.
### Watch out
Anything that would sound unnatural or rude, or common learner mistakes here.
{length}"""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]


class OllamaClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = (api_key or "").strip()
        self.model = model or DEFAULT_MODEL

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _request(self, path: str, body: dict | None = None, timeout: float = 90):
        headers = {"Content-Type": "application/json", "User-Agent": "zengo"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(BASE_URL + path, data=data, headers=headers)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            try:
                detail = json.loads(detail).get("error", detail)
            except ValueError:
                pass
            if e.code == 401:
                raise AIError("Ollama rejected the API key (401). Check it in Settings.") from None
            if e.code == 429:
                raise AIError("Ollama rate limit / free-tier quota reached. Try again later.") from None
            raise AIError(f"Ollama error {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            raise AIError(f"Can't reach ollama.com: {e.reason}") from None

    def models(self) -> list[str]:
        with self._request("/api/tags", timeout=15) as r:
            return [m["name"] for m in json.load(r)["models"]]

    def stream_chat(self, messages: Iterable[dict], on_chunk: Callable[[str], None],
                    should_stop: Callable[[], bool] = lambda: False) -> None:
        if not self.configured:
            raise AIError("No Ollama API key yet. Add it in Settings.")
        body = {"model": self.model, "messages": list(messages), "stream": True, "think": False}
        try:
            resp = self._request("/api/chat", body)
        except AIError as e:
            if "think" not in str(e).lower():
                raise
            body.pop("think")  # model doesn't support the think toggle
            resp = self._request("/api/chat", body)
        with resp:
            for line in resp:
                if should_stop():
                    return
                if not line.strip():
                    continue
                obj = json.loads(line)
                if obj.get("error"):
                    raise AIError(obj["error"])
                chunk = (obj.get("message") or {}).get("content")
                if chunk:
                    on_chunk(chunk)
                if obj.get("done"):
                    return
