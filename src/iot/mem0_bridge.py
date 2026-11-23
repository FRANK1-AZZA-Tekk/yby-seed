"""Grava episódios de sensor no Mem0 com dedupe e rate-limit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from src.iot.handlers import SensorEvent
from src.memory.episode_guard import DEFAULT_DEDUPE_SECONDS, DEFAULT_RATE_PER_MINUTE, EpisodeGuard

DEDUPE_SECONDS = DEFAULT_DEDUPE_SECONDS
RATE_LIMIT_PER_MINUTE = DEFAULT_RATE_PER_MINUTE


class Mem0Client(Protocol):
    """Contrato mínimo do cliente Mem0 (biblioteca ``mem0``)."""

    def add(self, messages: list[dict[str, str]], user_id: str = "yby", metadata: dict | None = None) -> Any:
        ...


Mem0Saver = Callable[[str, dict[str, Any]], None]


@dataclass
class EpisodeStore:
    """Adaptador IoT sobre :class:`EpisodeGuard` (API antiga com ``SensorEvent``)."""

    dedupe_window: float = DEFAULT_DEDUPE_SECONDS
    max_per_minute: int = DEFAULT_RATE_PER_MINUTE

    def __post_init__(self) -> None:
        self._guard = EpisodeGuard(
            dedupe_window=self.dedupe_window,
            max_per_minute=self.max_per_minute,
        )

    def should_accept(self, event: SensorEvent, *, now: float | None = None) -> bool:
        return self._guard.should_accept(event.sensor_id, _event_fingerprint(event), now=now)


def _event_to_text(event: SensorEvent) -> str:
    room = event.room or "desconhecido"
    return (
        f"Sensor {event.sensor_id} ({event.event_type.value}) em {room}: "
        f"valor={event.value!r} (tópico {event.topic})"
    )


def _event_fingerprint(event: SensorEvent) -> str:
    return f"{event.event_type.value}:{event.value!r}"


def save_episode(
    event: SensorEvent,
    *,
    mem0_client: Mem0Client | None = None,
    save_fn: Mem0Saver | None = None,
    user_id: str = "yby-iot",
    store: EpisodeGuard | EpisodeStore | None = None,
    now: float | None = None,
) -> bool:
    """
    Grava o evento no Mem0 se passar dedupe e rate-limit.

    Retorna True quando persistiu, False quando ignorado.
    """
    if isinstance(store, EpisodeStore):
        if not store.should_accept(event, now=now):
            return False
    else:
        guard = store or EpisodeGuard()
        if not guard.should_accept(event.sensor_id, _event_fingerprint(event), now=now):
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