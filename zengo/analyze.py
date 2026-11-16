"""Japanese sentence breakdown: tokens -> learner-friendly word chunks."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import fugashi

from .dictionary import Dictionary, has_kanji, kata_to_hira
from .grammar_data import AUXILIARIES, CFORM_NOTES, HELPERS, PARTICLES, POS_EN

NOUNISH = {"名詞", "接頭辞", "接尾辞", "形状詞", "代名詞"}
MERGEABLE = NOUNISH | {"動詞", "形容詞"}
SYMBOLS = {"補助記号", "記号", "空白"}
TE_LIKE = {"て", "で", "ば", "たり", "だり", "ちゃ", "じゃ"}
MAX_CHUNKS = 200

_JP_RE = re.compile(r"[぀-ヿ一-鿿ｦ-ﾟ々〆ヵヶ]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def is_japanese(text: str) -> bool:
    jp = len(_JP_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    return jp > 0 and jp * 3 >= latin  # one CJK char ~ several latin letters


def _is_kanji(c: str) -> bool:
    return "一" <= c <= "鿿" or c in "々〆ヵヶ"


def ruby(surface: str, reading: str | None) -> list[dict]:
    """Split a word into segments, attaching readings only above kanji runs."""
    if not reading or not has_kanji(surface):
        return [{"t": surface}]
    # Turn the surface into a regex: kana literal, kanji runs as groups.
    parts = re.findall(r"[一-鿿々〆ヵヶ]+|[^一-鿿々〆ヵヶ]+", surface)
    pattern = "".join("(.+?)" if _is_kanji(p[0]) else f"({re.escape(kata_to_hira(p))})" for p in parts)
    m = re.fullmatch(pattern, kata_to_hira(reading))
    if not m:
        return [{"t": surface, "r": reading}]
    out = []
    for p, g in zip(parts, m.groups()):
        out.append({"t": p, "r": g} if _is_kanji(p[0]) else {"t": p})
    return out


@dataclass
class Tok:
    surface: str
    pos1: str
    pos2: str
    ctype: str
    cform: str
    lemma: str
    base: str
    kana: str
    kana_base: str
    dict_reading: str | None = None  # set when merged into a dictionary compound


@dataclass
class Chunk:
    head: Tok
    parts: list[Tok] = field(default_factory=list)

    @property
    def toks(self) -> list[Tok]:
        return [self.head, *self.parts]


class Analyzer:
    def __init__(self, dictionary: Dictionary):
        self.d = dictionary
        self.tagger = fugashi.Tagger()

    # ---- tokenizing -------------------------------------------------------
    def tokenize(self, text: str) -> list[Tok]:
        out = []
        for w in self.tagger(text):
            f = w.feature
            lemma = (f.lemma or w.surface).split("-")[0]
            # MeCab drops whitespace; keep it so the sentence renders faithfully.
            if w.white_space:
                out.append(Tok(w.white_space, "空白", "", "*", "*", w.white_space, w.white_space, "", ""))
            out.append(Tok(
                surface=w.surface, pos1=f.pos1 or "", pos2=f.pos2 or "",
                ctype=f.cType or "*", cform=f.cForm or "*", lemma=lemma,
                base=f.orthBase or w.surface, kana=kata_to_hira(f.kana or ""),
                kana_base=kata_to_hira(f.kanaBase or ""),
            ))
        return out

    def merge_compounds(self, toks: list[Tok]) -> list[Tok]:
        """Greedy longest-match: join adjacent tokens that form a JMdict headword."""
        out, i = [], 0
        while i < len(toks):
            merged = None
            if toks[i].pos1 in MERGEABLE:
                for j in range(min(len(toks), i + 5), i + 1, -1):
                    span = toks[i:j]
                    if any(t.pos1 not in MERGEABLE for t in span):
                        continue
                    last = span[-1]
                    inflects = last.ctype != "*"
                    key = "".join(t.surface for t in span[:-1]) + (last.base if inflects else last.surface)
                    if len(key) > 1 and self.d.exists(key):
                        surface = "".join(t.surface for t in span)
                        entries = self.d.lookup(key, limit=1)
                        reading = entries[0]["reading"] if entries else None
                        prefix_kana = "".join(t.kana for t in span[:-1])
                        merged = Tok(
                            surface=surface, pos1=last.pos1 if inflects else span[0].pos1,
                            pos2=last.pos2, ctype=last.ctype, cform=last.cform,
                            lemma=key, base=key, kana="".join(t.kana for t in span),
                            kana_base=prefix_kana + last.kana_base, dict_reading=reading,
                        )
                        if reading and not inflects:
                            merged.kana = reading
                        i = j
                        break
            if merged is None:
                out.append(toks[i])
                i += 1
            else:
                out.append(merged)
        return out

    def chunk(self, toks: list[Tok]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for t in toks:
            prev = chunks[-1] if chunks else None
            prev_last = prev.toks[-1] if prev else None
            attach = False
            if prev and prev.head.pos1 not in SYMBOLS:
                if t.pos1 == "助動詞":
                    attach = True
                elif t.pos1 == "助詞" and t.pos2 == "接続助詞" and t.surface in TE_LIKE \
                        and prev_last.pos1 in {"動詞", "形容詞", "助動詞"}:
                    attach = True
                elif t.pos1 in {"動詞", "形容詞"} and t.pos2 == "非自立可能" \
                        and prev_last.surface in {"て", "で"}:
                    attach = True
                elif t.kana_base == "する" and not prev.parts and "サ変" in prev.head.pos2:
                    attach = True  # 勉強 + する -> suru-verb
            if attach:
                prev.parts.append(t)
            else:
                chunks.append(Chunk(t))
        return chunks

    # ---- describing -------------------------------------------------------
    @staticmethod
    def verb_class(t: Tok) -> str | None:
        c = t.ctype
        if c.startswith("五段"):
            return "godan verb"
        if c.startswith(("上一段", "下一段")):
            return "ichidan verb"
        if c.startswith("サ行変格"):
            return "suru verb (irregular)"
        if c.startswith("カ行変格"):
            return "kuru verb (irregular)"
        if c.startswith("形容詞"):
            return "i-adjective"
        return None

    def describe_parts(self, ch: Chunk) -> list[dict]:
        notes = []
        prev_lemma = ch.head.lemma
        for p in ch.parts:
            label = note = None
            if p.pos1 == "助動詞":
                label, note = AUXILIARIES.get(p.lemma, (None, None))
                if p.lemma in ("れる", "られる") and prev_lemma in ("せる", "させる") and notes:
                    prev = notes.pop()
                    notes.append({"t": prev["t"] + p.surface, "label": "causative-passive",
                                  "note": "Be made to do (often against one's will)."})
                    prev_lemma = p.lemma
                    continue
            elif p.pos1 == "助詞":
                label, note = PARTICLES.get(p.surface, ("te-form", ""))
            elif p.surface == "ください":
                label, note = HELPERS["ください"]
            else:
                label, note = HELPERS.get(p.kana_base, None) or HELPERS.get(p.lemma, (p.lemma, ""))
            if p.cform.startswith("仮定形") and p.lemma == "た":
                label, note = "conditional (たら)", "\"If / when\": once X happens."
            notes.append({"t": p.surface, "label": label or p.lemma, "note": note or ""})
            prev_lemma = p.lemma
        last = ch.toks[-1]
        for key, (label, note) in CFORM_NOTES.items():
            if last.cform.startswith(key) and not (last.lemma == "た" and key == "仮定形") \
                    and last.surface != "ください":
                notes.append({"t": "", "label": label, "note": note})
        return notes

    def lookup_chunk(self, h: Tok) -> list[dict]:
        tried = []
        for text, reading in ((h.lemma, h.kana_base), (h.base, h.kana_base), (h.surface, h.kana)):
            if text in tried or not text:
                continue
            tried.append(text)
            res = self.d.lookup(text, reading)
            if res:
                return res
        return []

    def analyze(self, text: str) -> dict:
        toks = self.merge_compounds(self.tokenize(text))
        chunks = self.chunk(toks)
        words, polite = [], False
        for idx, ch in enumerate(chunks[:MAX_CHUNKS]):
            h = ch.head
            if any(t.lemma in ("ます", "です") or t.surface in ("ください", "なさい", "ございます") for t in ch.toks):
                polite = True
            segs = []
            for t in ch.toks:
                segs += ruby(t.surface, t.dict_reading or t.kana)
            w = {
                "i": idx,
                "surface": "".join(t.surface for t in ch.toks),
                "segs": segs,
                "reading": "".join(t.kana for t in ch.toks),
                "pos": POS_EN.get(h.pos1, h.pos1),
                "pos_ja": h.pos1,
            }
            if h.pos1 in SYMBOLS:
                w["kind"] = "symbol"
            elif h.pos1 == "助詞":
                w["kind"] = "particle"
                label, note = PARTICLES.get(h.surface) or PARTICLES.get(h.lemma) or (None, None)
                if h.surface == "が" and h.pos2 == "接続助詞":
                    label, note = "but (conjunction)", "Joins two clauses: \"…, but …\"."
                elif h.surface == "の" and h.pos2 == "準体助詞":
                    label, note = "nominalizer", "Turns the preceding clause into a noun (\"the one that…\", \"the fact that…\")."
                w["grammar"] = {"label": label, "note": note} if label else None
                w["parts"] = self.describe_parts(ch)
                if not label:
                    w["entries"] = self.d.lookup(h.surface, limit=1)
            else:
                w["kind"] = "aux" if h.pos1 == "助動詞" else "word"
                w["base"] = h.lemma
                w["base_reading"] = h.dict_reading or h.kana_base
                w["inflected"] = w["surface"] != h.lemma
                w["vclass"] = self.verb_class(h)
                w["parts"] = self.describe_parts(ch)
                if h.pos1 == "助動詞" and h.lemma in AUXILIARIES:
                    label, note = AUXILIARIES[h.lemma]
                    w["grammar"] = {"label": label, "note": note}
                w["entries"] = self.lookup_chunk(h)
            words.append(w)

        seen, kanji = set(), []
        for c in text:
            if _is_kanji(c) and c not in seen and c not in "ヵヶ〆":
                seen.add(c)
                k = self.d.kanji(c)
                if k:
                    kanji.append(k)

        notes = []
        if any(w["kind"] != "symbol" for w in words):
            notes.append("Polite style (です/ます)" if polite else "Plain / casual style")
        keigo = {m for w in words if w["pos"] == "verb"
                 for e in w.get("entries", [])[:1] for s in e["senses"][:2] for m in s["misc"]
                 if "honorific" in m or "humble" in m or "polite" in m}
        notes += sorted(keigo)
        return {"words": words, "kanji": kanji[:40], "notes": notes, "truncated": len(chunks) > MAX_CHUNKS}
