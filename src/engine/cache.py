"""Cache local de respostas com TTL. Sem rede e sem disco."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass


@dataclass
class _Entry:
    text: str
    expires_at: float


class ResponseCache:
    """Dicionário em memória. TTL 0 desliga o cache."""

    def __init__(self, *, ttl_seconds: float, max_entries: int = 256) -> None:
        self.ttl_seconds = max(ttl_seconds, 0.0)
        self.max_entries = max(max_entries, 1)
        self._entries: dict[str, _Entry] = {}

    @property
    def enabled(self) -> bool:
        return self.ttl_seconds > 0

    def make_key(self, prompt: str, *, model: str, system: str) -> str:
        raw = f"{model}\0{system}\0{prompt}".encode()
        return hashlib.sha256(raw).hexdigest()

    def get(self, key: str) -> str | None:
        if not self.enabled:
            return None
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= time.monotonic():
            self._entries.pop(key, None)
            return None
        return entry.text

    def set(self, key: str, text: str) -> None:
        if not self.enabled:
            return
        if len(self._entries) >= self.max_entries:
            self._evict_expired_or_oldest()
        self._entries[key] = _Entry(text=text, expires_at=time.monotonic() + self.ttl_seconds)

    def clear(self) -> None:
        self._entries.clear()

    def _evict_expired_or_oldest(self) -> None:
        now = time.monotonic()
        expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)
        if len(self._entries) < self.max_entries:
            return
        oldest_key = min(self._entries, key=lambda k: self._entries[k].expires_at)
        self._entries.pop(oldest_key, None)
