"""Download JMdict (English) + KANJIDIC2 from scriptin/jmdict-simplified and
build a compact SQLite index at data/zengo.db.

Usage:  python scripts/build_dict.py [--force]
"""
from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from zengo import DICT_SCHEMA  # noqa: E402  (zengo/__init__.py is import-light)

RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "zengo.db"
API = "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "zengo-dict-builder"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def download_assets(force: bool) -> tuple[Path, Path]:
    RAW.mkdir(parents=True, exist_ok=True)
    existing_j = sorted(RAW.glob("jmdict-eng-*.json"))
    existing_k = sorted(RAW.glob("kanjidic2-en-*.json"))
    if existing_j and existing_k and not force:
        return existing_j[-1], existing_k[-1]

    release = json.loads(fetch(API))
    print("Latest release:", release["tag_name"])
    wanted = {}
    for a in release["assets"]:
        n = a["name"]
        if n.endswith(".json.zip") and (n.startswith("jmdict-eng-") and "common" not in n):
            wanted["jmdict"] = a
        elif n.endswith(".json.zip") and n.startswith("kanjidic2-en-"):
            wanted["kanjidic"] = a
    out = {}
    for key, a in wanted.items():
        print(f"Downloading {a['name']} ({a['size'] / 1e6:.1f} MB)...")
        data = fetch(a["browser_download_url"])
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = z.namelist()[0]
            target = RAW / name
            target.write_bytes(z.read(name))
            out[key] = target
    return out["jmdict"], out["kanjidic"]


def build(jmdict_path: Path, kanjidic_path: Path) -> None:
    # Build next to the real file and swap it in at the end, so a failed or interrupted build
    # never leaves Zengo without a dictionary.
    tmp = DB.with_suffix(".db.building")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(
        """
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE entries(id INTEGER PRIMARY KEY, common INTEGER, data TEXT);
        CREATE TABLE forms(text TEXT, entry_id INTEGER, kind TEXT, common INTEGER, pos INTEGER);
        CREATE TABLE kanji(literal TEXT PRIMARY KEY, data TEXT);
        """
    )

    print("Indexing JMdict...")
    jm = json.loads(jmdict_path.read_text(encoding="utf-8"))
    con.execute("INSERT INTO meta VALUES('tags', ?)", (json.dumps(jm["tags"], ensure_ascii=False),))
    con.execute("INSERT INTO meta VALUES('jmdict_version', ?)", (jm.get("dictDate", ""),))
    con.execute("INSERT INTO meta VALUES('schema', ?)", (str(DICT_SCHEMA),))
    entries, forms = [], []
    for w in jm["words"]:
        eid = int(w["id"])
        common = any(k.get("common") for k in w["kanji"]) or any(k.get("common") for k in w["kana"])
        compact = {
            "k": [{"t": k["text"], "c": k.get("common", False), "tags": k.get("tags", [])} for k in w["kanji"]],
            "r": [
                {"t": r["text"], "c": r.get("common", False), "tags": r.get("tags", []),
                 "ak": r.get("appliesToKanji", ["*"])}
                for r in w["kana"]
            ],
            "s": [
                {
                    "pos": s.get("partOfSpeech", []),
                    "g": [g["text"] for g in s.get("gloss", []) if g.get("lang", "eng") == "eng"],
                    "misc": s.get("misc", []),
                    "field": s.get("field", []),
                    "dial": s.get("dialect", []),
                    "info": s.get("info", []),
                    "ak": s.get("appliesToKanji", ["*"]),
                    "ar": s.get("appliesToKana", ["*"]),
                }
                for s in w["sense"]
            ],
        }
        entries.append((eid, int(common), json.dumps(compact, ensure_ascii=False, separators=(",", ":"))))
        for i, k in enumerate(w["kanji"]):
            forms.append((k["text"], eid, "k", int(k.get("common", False)), i))
        for i, r in enumerate(w["kana"]):
            forms.append((r["text"], eid, "r", int(r.get("common", False)), i))
    con.executemany("INSERT INTO entries VALUES(?,?,?)", entries)
    con.executemany("INSERT INTO forms VALUES(?,?,?,?,?)", forms)
    con.execute("CREATE INDEX forms_text ON forms(text)")
    print(f"  {len(entries):,} entries, {len(forms):,} forms")

    print("Indexing KANJIDIC2...")
    kd = json.loads(kanjidic_path.read_text(encoding="utf-8"))
    rows = []
    for c in kd["characters"]:
        on, kun, meanings = [], [], []
        rm = c.get("readingMeaning") or {}
        for grp in rm.get("groups", []):
            for r in grp.get("readings", []):
                if r["type"] == "ja_on":
                    on.append(r["value"])
                elif r["type"] == "ja_kun":
                    kun.append(r["value"])
            meanings += [m["value"] for m in grp.get("meanings", []) if m.get("lang", "en") == "en"]
        misc = c.get("misc", {})
        rows.append((c["literal"], json.dumps({
            "on": on, "kun": kun, "m": meanings, "nanori": rm.get("nanori", []),
            "grade": misc.get("grade"), "jlpt": misc.get("jlptLevel"),
            "strokes": (misc.get("strokeCounts") or [None])[0], "freq": misc.get("frequency"),
        }, ensure_ascii=False, separators=(",", ":"))))
    con.executemany("INSERT INTO kanji VALUES(?,?)", rows)
    print(f"  {len(rows):,} kanji")
    con.commit()
    con.execute("VACUUM")
    con.close()
    try:
        os.replace(tmp, DB)
    except PermissionError:
        sys.exit(f"{DB} is in use. Quit Zengo (tray icon -> Quit) and run this again.")
    print("Built", DB, f"({DB.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    j, k = download_assets(force="--force" in sys.argv)
    build(j, k)
