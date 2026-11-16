"""Contratos versionados hub↔dispositivo (v1). Sem firmware / sem transporte real."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

DEVICE_SCHEMA = "yby-device/v1"
DeviceKind = Literal["watch", "phone", "hub", "fake"]
IntentAction = Literal["notify", "vibrate", "display", "ping"]
ALLOWED_ACTIONS: tuple[str, ...] = ("notify", "vibrate", "display", "ping")


class DeviceError(ValueError):
    """JSON inválido, schema errado ou ação fora da allowlist de intents."""


class DeviceIdentity(BaseModel):
    """Identidade lógica do nó. `firmware` é só string de metadado (não flashea)."""

    device_id: str = Field(min_length=1, max_length=64)
    kind: DeviceKind = "fake"
    firmware: str | None = Field(default=None, max_length=64)


class TelemetryEvent(BaseModel):
    """Telemetria sintética ou futura; não aciona hardware."""

    schema_version: Literal["yby-device/v1"] = DEVICE_SCHEMA
    type: Literal["telemetry"] = "telemetry"
    event_id: str = Field(min_length=1, max_length=64)
    device: DeviceIdentity
    ts: str
    sensors: dict[str, float | int | str | bool] = Field(default_factory=dict)


class CommandIntent(BaseModel):
    """Intent allowlisted. Validar ≠ executar no relógio/celular."""

    schema_version: Literal["yby-device/v1"] = DEVICE_SCHEMA
    type: Literal["intent"] = "intent"
    event_id: str = Field(min_length=1, max_length=64)
    device: DeviceIdentity
    ts: str
    action: IntentAction
    payload: dict[str, str] = Field(default_factory=dict)


DeviceMessage = Annotated[
    Union[TelemetryEvent, CommandIntent],
    Field(discriminator="type"),
]

_ADAPTER: TypeAdapter[TelemetryEvent | CommandIntent] = TypeAdapter(DeviceMessage)


def new_event_id() -> str:
    return uuid4().hex[:16]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_message(data: object) -> TelemetryEvent | CommandIntent:
    """Valida dict/JSON-compatível contra o contrato v1."""

    try:
        return _ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise DeviceError(f"mensagem de dispositivo inválida: {exc.errors()[0]['msg']}") from exc


def parse_message_json(raw: str | bytes) -> TelemetryEvent | CommandIntent:
    try:
        return _ADAPTER.validate_json(raw)
    except ValidationError as exc:
        raise DeviceError(f"JSON de dispositivo inválido: {exc.errors()[0]['msg']}") from exc
