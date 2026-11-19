"""SQLite-backed lookups into JMdict and KANJIDIC2 (built by scripts/build_dict.py)."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from functools import lru_cache
from pathlib import Path

from . import DICT_SCHEMA

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "zengo.db"


class DictionaryError(RuntimeError):
    pass


def installed_schema(path: Path = DB_PATH) -> int | None:
    """Schema of the built dictionary, None if missing or unreadable. 1.0 builds had no
    schema row and are schema 1."""
    if not path.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = con.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
        finally:
            con.close()
        return int(row[0]) if row else 1
    except (sqlite3.Error, ValueError):
        return None


def kata_to_hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def has_kanji(s: str) -> bool:
    return any("一" <= c <= "鿿" or c == "々" for c in s)


class Dictionary:
    def __init__(self, path: Path = DB_PATH):
        schema = installed_schema(path)
        if schema is None:
            raise DictionaryError("The dictionary (data\\zengo.db) is missing or damaged.\n\n"
                                  "Run setup.bat in the Zengo folder to build it.")
        if schema < DICT_SCHEMA:
            raise DictionaryError("This version of Zengo needs a newer dictionary.\n\n"
                                  "Run update.bat (or setup.bat) in the Zengo folder to rebuild it.")
        self._path = path
        self._local = threading.local()
        self.tags: dict[str, str] = json.loads(
            self._con().execute("SELECT value FROM meta WHERE key='tags'").fetchone()[0]
        )

    @property
    def version(self) -> str:
        row = self._con().execute("SELECT value FROM meta WHERE key='jmdict_version'").fetchone()
        return row[0] if row else ""

    def _con(self) -> sqlite3.Connection:
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(f"file:{self._path}?mode=ro", uri=True, check_same_thread=False)
            self._local.con = con
        return con

    @lru_cache(maxsize=50_000)
    def exists(self, text: str) -> bool:
        return self._con().execute("SELECT 1 FROM forms WHERE text=? LIMIT 1", (text,)).fetchone() is not None

    @lru_cache(maxsize=2_000)
    def tag(self, t: str) -> str:
        # "noun (common) (futsuumeishi)" -> "noun (common)"
        return re.sub(r"\s*\([a-z'\-]+\)$", "", self.tags.get(t, t))

    @lru_cache(maxsize=5_000)
    def _lookup_cached(self, text: str, reading: str | None, limit: int) -> tuple:
        rows = self._con().execute(
            "SELECT f.entry_id, f.kind, f.common, f.pos, e.data FROM forms f "
            "JOIN entries e ON e.id = f.entry_id WHERE f.text=?",
            (text,),
        ).fetchall()
        reading_h = kata_to_hira(reading) if reading else None
        scored: dict[int, tuple[float, str, dict]] = {}
        for eid, kind, common, pos, data in rows:
            d = json.loads(data)
            score = 0.0
            if common:
                score += 10
            if kind == "k":
                score += 3
            score -= pos * 0.5
            if reading_h and any(r["t"] == reading_h for r in d["r"]):
                score += 6
            if kind == "r" and has_kanji(text) is False and d["k"]:
                # matched only by kana; if word is usually kana it's still fine
                if any("uk" in s["misc"] for s in d["s"]):
                    score += 2
                else:
                    score -= 2
            prev = scored.get(eid)
            if prev is None or score > prev[0]:
                scored[eid] = (score, kind, d)
        best = sorted(scored.items(), key=lambda kv: -kv[1][0])[:limit]
        return tuple(self._format(eid, text, kind, d) for eid, (score, kind, d) in best)

    def lookup(self, text: str, reading: str | None = None, limit: int = 3) -> list[dict]:
        return list(self._lookup_cached(text, reading, limit))

    def _format(self, eid: int, matched: str, kind: str, d: dict) -> dict:
        # Choose the headword + reading that applies to what we matched.
        if kind == "k":
            head = matched
            reading = next((r["t"] for r in d["r"] if "*" in r["ak"] or matched in r["ak"]), d["r"][0]["t"])
        else:
            reading = matched
            head = next((k["t"] for k in d["k"]), matched)
            if any("uk" in s["misc"] for s in d["s"][:2]):
                head = matched
        senses = []
        last_pos: list[str] = []
        for s in d["s"]:
            if kind == "k" and "*" not in s["ak"] and matched not in s["ak"]:
                continue
            pos = s["pos"] or last_pos
            last_pos = pos
            senses.append({
                "pos": [self.tag(p) for p in pos],
                "glosses": s["g"],
                "misc": [self.tag(m) for m in s["misc"]],
                "field": [self.tag(f) for f in s["field"]],
                "dialect": [self.tag(x) for x in s["dial"]],
                "info": s["info"],
            })
        return {
            "id": eid,
            "head": head,
            "reading": reading,
            "other_forms": [k["t"] for k in d["k"] if k["t"] != head][:4],
            "common": any(k["c"] for k in d["k"]) or any(r["c"] for r in d["r"]),
            "senses": senses[:6],
        }

    @lru_cache(maxsize=5_000)
    def kanji(self, ch: str) -> dict | None:
        row = self._con().execute("SELECT data FROM kanji WHERE literal=?", (ch,)).fetchone()
        if not row:
            return None
        d = json.loads(row[0])
        d["literal"] = ch
        return d
