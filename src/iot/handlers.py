"""Parse e validação de mensagens MQTT de sensores domésticos."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

_EVENT_SUFFIXES = frozenset({"presence", "temperature", "door", "motion"})


class IoTEventType(str, Enum):
    """Tipos de evento suportados no v1."""

    PRESENCE = "presence"
    TEMPERATURE = "temperature"
    DOOR = "door"
    MOTION = "motion"


@dataclass(frozen=True)
class SensorEvent:
    """Evento normalizado a partir de um tópico + payload."""

    sensor_id: str
    event_type: IoTEventType
    value: Any
    room: str | None
    topic: str
    received_at: float
    raw: dict[str, Any]


class PayloadValidationError(ValueError):
    """Payload JSON inválido para o schema YBY."""


def _event_type_from_topic(topic: str) -> tuple[IoTEventType, str, str | None]:
    """
    Espera ``yby/sensors/{room}/{sensor_id}/{kind}`` ou ``yby/sensors/{room}/{kind}``.

    ``kind`` deve ser presence, temperature, door ou motion.
    """
    parts = [segment for segment in topic.split("/") if segment]
    if len(parts) < 4 or parts[0] != "yby" or parts[1] != "sensors":
        raise PayloadValidationError(f"tópico fora do padrão yby/sensors: {topic}")

    kind = parts[-1].lower()
    if kind not in _EVENT_SUFFIXES:
        raise PayloadValidationError(f"tipo de evento desconhecido no tópico: {kind}")

    event_type = IoTEventType(kind)
    room = parts[2]
    if len(parts) == 4:
        sensor_id = parts[2]
    elif len(parts) == 5:
        sensor_id = parts[3]
    else:
        sensor_id = "/".join(parts[3:-1])
    return event_type, sensor_id, room


def validate_payload(data: dict[str, Any]) -> Any:
    """Schema mínimo: objeto com chave ``value``."""
    if not isinstance(data, dict):
        raise PayloadValidationError("payload deve ser um objeto JSON")
    if "value" not in data:
        raise PayloadValidationError('payload deve conter a chave "value"')
    return data["value"]


def parse_message_safe(topic: str, payload: bytes | str) -> SensorEvent | None:
    """
    Igual a :func:`parse_message`, mas rejeita payloads inválidos com log estruturado.

    Não registra o corpo da mensagem (D10).
    """

    try:
        return parse_message(topic, payload)
    except PayloadValidationError as exc:
        logger.warning(
            "iot_payload_rejected",
            extra={
                "topic": topic,
                "error_type": type(exc).__name__,
                "reason": str(exc),
            },
        )
        return None


def parse_message(topic: str, payload: bytes | str) -> SensorEvent:
    """Converte mensagem MQTT em ``SensorEvent``."""
    event_type, sensor_id, room = _event_type_from_topic(topic)

    if isinstance(payload, bytes):
        text = payload.decode("utf-8")
    else:
        text = payload

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PayloadValidationError("payload não é JSON válido") from exc

    value = validate_payload(data)
    received = data.get("ts")
    received_at = float(received) if isinstance(received, (int, float)) else time.time()

    return SensorEvent(
        sensor_id=sensor_id,
        event_type=event_type,
        value=value,
        room=room,
        topic=topic,
        received_at=received_at,
        raw=data if isinstance(data, dict) else {"value": value},
    )