"""DeepL wrapper. Direction is picked automatically: Japanese in -> English out,
anything else -> Japanese out."""
from __future__ import annotations

from collections import OrderedDict

import deepl

from .analyze import is_japanese


class Translator:
    def __init__(self, config):
        self.config = config
        self._client = None
        self._client_key = None
        self._cache: OrderedDict[tuple, dict] = OrderedDict()

    def _get_client(self):
        key = (self.config["deepl_key"] or "").strip()
        if not key:
            raise RuntimeError("No DeepL API key yet. Add it in Settings.")
        if key != self._client_key:
            self._client, self._client_key = deepl.Translator(key), key
        return self._client

    @property
    def configured(self) -> bool:
        return bool((self.config["deepl_key"] or "").strip())

    def direction(self, text: str) -> tuple[str, str]:
        return ("JA", self.config["en_variant"]) if is_japanese(text) else ("EN", "JA")

    def translate(self, text: str) -> dict:
        src, tgt = self.direction(text)
        formality = self.config["ja_formality"] if tgt == "JA" else "default"
        ck = (text, tgt, formality)
        if ck in self._cache:
            self._cache.move_to_end(ck)
            return self._cache[ck]
        kwargs = {"formality": formality} if formality != "default" else {}
        # Let DeepL auto-detect the source; we only choose the target.
        r = self._get_client().translate_text(text, target_lang=tgt, **kwargs)
        out = {"text": r.text, "detected": r.detected_source_lang, "source": src, "target": tgt}
        self._cache[ck] = out
        if len(self._cache) > 300:
            self._cache.popitem(last=False)
        return out

    def usage(self) -> dict:
        u = self._get_client().get_usage().character
        return {"used": u.count, "limit": u.limit}
