"""Contratos versionados de dispositivos + transporte fake (lote 27)."""

from src.devices.fake import FakeDeviceBus, SimulationReport, format_simulation
from src.devices.schemas import (
    ALLOWED_ACTIONS,
    DEVICE_SCHEMA,
    CommandIntent,
    DeviceError,
    DeviceIdentity,
    TelemetryEvent,
    parse_message,
    parse_message_json,
)

__all__ = [
    "ALLOWED_ACTIONS",
    "DEVICE_SCHEMA",
    "CommandIntent",
    "DeviceError",
    "DeviceIdentity",
    "FakeDeviceBus",
    "SimulationReport",
    "TelemetryEvent",
    "format_simulation",
    "parse_message",
    "parse_message_json",
]
