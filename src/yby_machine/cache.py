"""Cache em processo de YBYSpec por fingerprint do prompt (sem Redis/pgvector)."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.yby_machine.translator import TranslateResult


def prompt_fingerprint(prompt: str) -> str:
    """Hash estável do prompt (casefold + strip) para reuso local."""

    normalized = (prompt or "").strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class SpecFingerprintCache:
    """LRU mínimo em memória. Interface pronta se Redis/pgvector vierem depois."""

    def __init__(self, max_size: int = 64) -> None:
        if max_size < 1:
            raise ValueError("max_size deve ser >= 1")
        self._max_size = max_size
        self._store: OrderedDict[str, TranslateResult] = OrderedDict()

    def get(self, prompt: str) -> TranslateResult | None:
        key = prompt_fingerprint(prompt)
        hit = self._store.get(key)
        if hit is None:
            return None
        self._store.move_to_end(key)
        return hit

    def put(self, prompt: str, result: TranslateResult) -> None:
        key = prompt_fingerprint(prompt)
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = result
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)


DEFAULT_SPEC_CACHE = SpecFingerprintCache()
