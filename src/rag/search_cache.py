"""Cache em memória de embeddings e buscas (TTL, sem GPU)."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class TtlCache(Generic[T]):
    """Cache TTL simples para embeddings e hits de busca."""

    ttl_seconds: float = 300.0
    _store: dict[str, tuple[T, float]] = field(default_factory=dict)

    def _purge(self, now: float) -> None:
        expired = [key for key, (_val, stamp) in self._store.items() if now - stamp > self.ttl_seconds]
        for key in expired:
            del self._store[key]

    def get(self, key: str, *, now: float | None = None) -> T | None:
        clock = time.time() if now is None else now
        self._purge(clock)
        row = self._store.get(key)
        if row is None:
            return None
        value, stamp = row
        if clock - stamp > self.ttl_seconds:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: T, *, now: float | None = None) -> None:
        clock = time.time() if now is None else now
        self._purge(clock)
        self._store[key] = (value, clock)


def cache_key(prefix: str, *parts: Any) -> str:
    """Chave estável sem expor conteúdo nos logs."""

    raw = "|".join(f"{prefix}:{part!r}" for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


@dataclass
class RagCaches:
    """Caches separados para embedding e resultados de busca."""

    embedding: TtlCache[list[float]] = field(default_factory=lambda: TtlCache(ttl_seconds=600.0))
    search: TtlCache[list[dict[str, Any]]] = field(default_factory=lambda: TtlCache(ttl_seconds=120.0))