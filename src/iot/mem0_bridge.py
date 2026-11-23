"""Grava episódios de sensor no Mem0 com dedupe e rate-limit."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from src.iot.handlers import SensorEvent

DEDUPE_SECONDS = 5.0
RATE_LIMIT_PER_MINUTE = 10


class Mem0Client(Protocol):
    """Contrato mínimo do cliente Mem0 (biblioteca ``mem0``)."""

    def add(self, messages: list[dict[str, str]], user_id: str = "yby", metadata: dict | None = None) -> Any:
        ...


Mem0Saver = Callable[[str, dict[str, Any]], None]


@dataclass
class EpisodeStore:
    """Controla dedupe e rate-limit por sensor."""

    dedupe_window: float = DEDUPE_SECONDS
    max_per_minute: int = RATE_LIMIT_PER_MINUTE
    _last_fingerprint: dict[str, tuple[str, float]] = field(default_factory=dict)
    _timestamps: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def _fingerprint(self, event: SensorEvent) -> str:
        return f"{event.event_type.value}:{event.value!r}"

    def should_accept(self, event: SensorEvent, *, now: float | None = None) -> bool:
        """Retorna False se duplicado (<5s) ou acima de 10 eventos/min."""
        clock = now if now is not None else time.time()
        sensor = event.sensor_id
        fp = self._fingerprint(event)

        last = self._last_fingerprint.get(sensor)
        if last is not None and last[0] == fp and clock - last[1] < self.dedupe_window:
            return False

        window = self._timestamps[sensor]
        while window and clock - window[0] > 60.0:
            window.popleft()
        if len(window) >= self.max_per_minute:
            return False

        window.append(clock)
        self._last_fingerprint[sensor] = (fp, clock)
        return True


def _event_to_text(event: SensorEvent) -> str:
    room = event.room or "desconhecido"
    return (
        f"Sensor {event.sensor_id} ({event.event_type.value}) em {room}: "
        f"valor={event.value!r} (tópico {event.topic})"
    )


def save_episode(
    event: SensorEvent,
    *,
    mem0_client: Mem0Client | None = None,
    save_fn: Mem0Saver | None = None,
    user_id: str = "yby-iot",
    store: EpisodeStore | None = None,
    now: float | None = None,
) -> bool:
    """
    Grava o evento no Mem0 se passar dedupe e rate-limit.

    Retorna True quando persistiu, False quando ignorado.
    """
    guard = store or EpisodeStore()
    if not guard.should_accept(event, now=now):
        return False

    text = _event_to_text(event)
    metadata = {
        "sensor_id": event.sensor_id,
        "event_type": event.event_type.value,
        "room": event.room,
        "topic": event.topic,
        "value": event.value,
    }

    if save_fn is not None:
        save_fn(text, metadata)
        return True

    if mem0_client is not None:
        mem0_client.add(
            [{"role": "user", "content": text}],
            user_id=user_id,
            metadata=metadata,
        )
        return True

    raise ValueError("Informe mem0_client ou save_fn para persistir o episódio.")