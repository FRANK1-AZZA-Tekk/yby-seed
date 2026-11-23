"""Tools LangGraph para consultar estado atual dos sensores (memória em processo)."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from typing import Any, Callable

from src.iot.handlers import SensorEvent


@dataclass(frozen=True)
class SensorSnapshot:
    """Estado serializável de um sensor."""

    sensor_id: str
    event_type: str
    value: Any
    room: str | None
    topic: str
    received_at: float


class SensorStateStore:
    """Armazena último estado por sensor (thread-safe, só CPU)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, SensorSnapshot] = {}

    def update(self, event: SensorEvent) -> None:
        snap = SensorSnapshot(
            sensor_id=event.sensor_id,
            event_type=event.event_type.value,
            value=event.value,
            room=event.room,
            topic=event.topic,
            received_at=event.received_at,
        )
        with self._lock:
            self._states[event.sensor_id] = snap

    def get(self, sensor_id: str) -> SensorSnapshot | None:
        with self._lock:
            return self._states.get(sensor_id)

    def list_sensor_ids(self) -> list[str]:
        with self._lock:
            return sorted(self._states.keys())


_DEFAULT_STORE = SensorStateStore()


def get_default_store() -> SensorStateStore:
    return _DEFAULT_STORE


def get_sensor_state(sensor_id: str, store: SensorStateStore | None = None) -> dict[str, Any] | None:
    """Retorna estado atual do sensor ou None."""
    target = store or _DEFAULT_STORE
    snap = target.get(sensor_id)
    if snap is None:
        return None
    return asdict(snap)


def list_sensors(store: SensorStateStore | None = None) -> list[dict[str, Any]]:
    """Lista sensores com estado conhecido."""
    target = store or _DEFAULT_STORE
    result: list[dict[str, Any]] = []
    for sensor_id in target.list_sensor_ids():
        snap = target.get(sensor_id)
        if snap is not None:
            result.append(asdict(snap))
    return result


def register_iot_tools(
    store: SensorStateStore | None = None,
) -> list[dict[str, Any]]:
    """
    Adiciona tools consultáveis ao LangGraph.

    Cada entrada tem ``name``, ``description`` e ``func`` (callable).
    """
    target = store or _DEFAULT_STORE

    def _get(sensor_id: str) -> str:
        state = get_sensor_state(sensor_id, target)
        if state is None:
            return json.dumps({"error": "sensor não encontrado", "sensor_id": sensor_id}, ensure_ascii=False)
        return json.dumps(state, ensure_ascii=False)

    def _list() -> str:
        return json.dumps(list_sensors(target), ensure_ascii=False)

    tools: list[dict[str, Callable[..., str] | str]] = [
        {
            "name": "get_sensor_state",
            "description": "Estado atual de um sensor doméstico (presença, temperatura, porta, movimento).",
            "func": _get,
        },
        {
            "name": "list_sensors",
            "description": "Lista sensores domésticos com leitura recente no PC Hub.",
            "func": _list,
        },
    ]
    return tools