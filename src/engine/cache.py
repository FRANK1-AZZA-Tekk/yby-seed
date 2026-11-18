"""Cache local de respostas com TTL. Opcionalmente persiste em disco.

O CLI `ask` termina a cada pedido. Sem arquivo, o TTL não sobrevive ao
processo e o mesmo prompt volta a queimar GPU ou cota de nuvem.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class _Entry:
    text: str
    expires_at: float


class ResponseCache:
    """Dicionário com TTL. TTL 0 desliga o cache. `path` grava entre processos."""

    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_entries: int = 256,
        path: Path | None = None,
    ) -> None:
        self.ttl_seconds = max(ttl_seconds, 0.0)
        self.max_entries = max(max_entries, 1)
        self.path = path
        self._entries: dict[str, _Entry] = {}
        if path is not None and self.enabled:
            self._load()

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
        if entry.expires_at <= time.time():
            self._entries.pop(key, None)
            return None
        return entry.text

    def set(self, key: str, text: str) -> None:
        if not self.enabled:
            return
        if key not in self._entries and len(self._entries) >= self.max_entries:
            self._evict_expired_or_oldest()
        self._entries[key] = _Entry(text=text, expires_at=time.time() + self.ttl_seconds)
        self._save()

    def clear(self) -> None:
        self._entries.clear()
        self._save()

    def _evict_expired_or_oldest(self) -> None:
        now = time.time()
        expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)
        if len(self._entries) < self.max_entries:
            return
        oldest_key = min(self._entries, key=lambda k: self._entries[k].expires_at)
        self._entries.pop(oldest_key, None)

    def _load(self) -> None:
        if self.path is None or not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return
        entries = raw.get("entries") if isinstance(raw, dict) else None
        if not isinstance(entries, dict):
            return
        now = time.time()
        loaded: dict[str, _Entry] = {}
        for key, item in entries.items():
            if not isinstance(key, str) or not isinstance(item, dict):
                continue
            text = item.get("text")
            expires = item.get("expires_at")
            if not isinstance(text, str) or not isinstance(expires, (int, float)):
                continue
            if float(expires) <= now:
                continue
            loaded[key] = _Entry(text=text, expires_at=float(expires))
        if len(loaded) > self.max_entries:
            keep = sorted(loaded, key=lambda k: loaded[k].expires_at, reverse=True)
            loaded = {key: loaded[key] for key in keep[: self.max_entries]}
        self._entries = loaded

    def _save(self) -> None:
        if self.path is None or not self.enabled:
            return
        payload = {
            "entries": {
                key: {"text": entry.text, "expires_at": entry.expires_at}
                for key, entry in self._entries.items()
            }
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
        except OSError:
            return
