"""Lote 27: contratos versionados + bus fake (sem firmware / sem rede)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from src.devices.fake import FakeDeviceBus
from src.devices.schemas import (
    DEVICE_SCHEMA,
    CommandIntent,
    DeviceError,
    TelemetryEvent,
    parse_message,
    parse_message_json,
)
from src.main import cli


def test_parse_telemetry_and_intent() -> None:
    bus = FakeDeviceBus(device_id="dev-a")
    tel = bus.emit_telemetry({"battery_pct": 50})
    assert isinstance(tel, TelemetryEvent)
    assert tel.schema_version == DEVICE_SCHEMA
    assert tel.type == "telemetry"
    assert parse_message(tel.model_dump()).type == "telemetry"

    intent = bus.make_intent("notify", payload={"text": "oi"})
    assert isinstance(intent, CommandIntent)
    assert intent.action == "notify"
    again = parse_message_json(intent.model_dump_json())
    assert again.type == "intent"
    assert again.event_id == intent.event_id


def test_acao_fora_allowlist() -> None:
    with pytest.raises(DeviceError, match="allowlist"):
        FakeDeviceBus().make_intent("reboot")


def test_json_invalido() -> None:
    with pytest.raises(DeviceError):
        parse_message({"type": "telemetry", "event_id": ""})
    with pytest.raises(DeviceError):
        parse_message_json("{not-json")


def test_simulate_nao_executa() -> None:
    report = FakeDeviceBus().simulate(action="ping")
    assert report.transport == "fake"
    assert report.accepted is True
    assert report.executed is False
    assert "firmware" in report.warning.casefold() or "mqtt" in report.warning.casefold()
    assert report.intent.action == "ping"


def test_cli_schema_validate_simulate(tmp_path: Path) -> None:
    runner = CliRunner()
    schema = runner.invoke(cli, ["devices", "schema"])
    assert schema.exit_code == 0, schema.output
    assert DEVICE_SCHEMA in schema.output
    assert "ping" in schema.output

    bus = FakeDeviceBus(device_id="cli-dev")
    path = tmp_path / "intent.json"
    path.write_text(bus.make_intent("vibrate").model_dump_json(indent=2), encoding="utf-8")
    validated = runner.invoke(cli, ["devices", "validate", str(path)])
    assert validated.exit_code == 0, validated.output
    assert "ok:" in validated.output
    assert "vibrate" not in validated.output or "intent" in validated.output

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"type": "intent", "action": "explode"}), encoding="utf-8")
    denied = runner.invoke(cli, ["devices", "validate", str(bad)])
    assert denied.exit_code == 1

    sim = runner.invoke(cli, ["devices", "simulate", "--action", "display", "--json"])
    assert sim.exit_code == 0, sim.output
    payload = json.loads(sim.output)
    assert payload["executed"] is False
    assert payload["transport"] == "fake"
    assert payload["intent"]["action"] == "display"
