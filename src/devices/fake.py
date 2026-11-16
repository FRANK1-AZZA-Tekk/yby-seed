"""Barramento fake: gera/valida mensagens sem MQTT, BLE ou firmware."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from src.devices.schemas import (
    ALLOWED_ACTIONS,
    DEVICE_SCHEMA,
    CommandIntent,
    DeviceError,
    DeviceIdentity,
    DeviceKind,
    IntentAction,
    TelemetryEvent,
    new_event_id,
    parse_message,
    utc_now,
)


class SimulationReport(BaseModel):
    """Resultado de simulate: contrato ok, hardware não tocado."""

    schema_version: Literal["yby-device/v1"] = DEVICE_SCHEMA
    transport: Literal["fake"] = "fake"
    warning: str = (
        "transporte fake: sem MQTT/BLE/firmware; intent não executado no dispositivo"
    )
    telemetry: TelemetryEvent
    intent: CommandIntent
    accepted: bool = True
    executed: bool = False


class FakeDeviceBus:
    """Emite telemetria e intents sintéticos; só valida o contrato."""

    def __init__(
        self, *, device_id: str = "fake-watch-1", kind: DeviceKind = "fake"
    ) -> None:
        self.identity = DeviceIdentity(
            device_id=device_id, kind=kind, firmware="fake-0"
        )

    def emit_telemetry(
        self,
        sensors: dict[str, float | int | str | bool] | None = None,
    ) -> TelemetryEvent:
        return TelemetryEvent(
            event_id=new_event_id(),
            device=self.identity,
            ts=utc_now(),
            sensors=sensors
            or {
                "battery_pct": 87,
                "heart_rate_bpm": 72,
                "source": "fake",
            },
        )

    def make_intent(
        self,
        action: IntentAction | str,
        *,
        payload: dict[str, str] | None = None,
    ) -> CommandIntent:
        if action not in ALLOWED_ACTIONS:
            raise DeviceError(
                f"ação '{action}' fora da allowlist: {', '.join(ALLOWED_ACTIONS)}"
            )
        typed: IntentAction = action  # type: ignore[assignment]
        return CommandIntent(
            event_id=new_event_id(),
            device=self.identity,
            ts=utc_now(),
            action=typed,
            payload=payload or {},
        )

    def simulate(
        self,
        *,
        action: IntentAction | str = "ping",
        payload: dict[str, str] | None = None,
    ) -> SimulationReport:
        telemetry = self.emit_telemetry()
        intent = self.make_intent(action, payload=payload)
        # Round-trip pelo validador (como o hub faria antes de qualquer firmware).
        parsed = parse_message(intent.model_dump())
        if not isinstance(parsed, CommandIntent):
            raise DeviceError("intent fake não revalidou como CommandIntent")
        return SimulationReport(telemetry=telemetry, intent=parsed)


def format_simulation(report: SimulationReport) -> str:
    lines = [
        f"schema: {report.schema_version}",
        f"transport: {report.transport}",
        f"warning: {report.warning}",
        f"accepted: {report.accepted} executed: {report.executed}",
        (
            f"telemetry: id={report.telemetry.event_id} "
            f"device={report.telemetry.device.device_id} "
            f"sensors={report.telemetry.sensors}"
        ),
        (
            f"intent: id={report.intent.event_id} action={report.intent.action} "
            f"payload={report.intent.payload}"
        ),
    ]
    return "\n".join(lines)
