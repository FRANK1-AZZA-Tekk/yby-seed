"""Dedupe e rate-limit de episódios (Mem0 / sensores / vault)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

DEFAULT_DEDUPE_SECONDS = 5.0
DEFAULT_RATE_PER_MINUTE = 10


@dataclass
class EpisodeGuard:
    """
    Ignora o mesmo conteúdo em ``dedupe_window`` segundos.

    Limita ``max_per_minute`` aceites por ``source_id`` (fonte do episódio).
    """

    dedupe_window: float = DEFAULT_DEDUPE_SECONDS
    max_per_minute: int = DEFAULT_RATE_PER_MINUTE
    _last_fingerprint: dict[str, tuple[str, float]] = field(default_factory=dict)
    _timestamps: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def should_accept(
        self,
        source_id: str,
        fingerprint: str,
        *,
        now: float | None = None,
    ) -> bool:
        """Retorna False se duplicado ou acima do rate-limit."""
        clock = time.time() if now is None else now
        last = self._last_fingerprint.get(source_id)
        if last is not None and last[0] == fingerprint and clock - last[1] < self.dedupe_window:
            return False

        window = self._timestamps[source_id]
        while window and clock - window[0] > 60.0:
            window.popleft()
        if len(window) >= self.max_per_minute:
            return False

        window.append(clock)
        self._last_fingerprint[source_id] = (fingerprint, clock)
        return True


def episode_fingerprint(text: str, metadata: dict[str, object] | None = None) -> str:
    """Fingerprint estável para dedupe (não inclui dados sensíveis extras)."""

    meta_bit = ""
    if metadata:
        kind = metadata.get("event_type") or metadata.get("kind") or ""
        value = metadata.get("value")
        meta_bit = f"|{kind!r}:{value!r}"
    return f"{text.strip()}{meta_bit}"