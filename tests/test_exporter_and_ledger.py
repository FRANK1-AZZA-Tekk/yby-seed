"""Exporter, serial probe, ledger e rotas /v1/seed/*."""

from __future__ import annotations

import io
import zipfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.yby_seed.agents.state import MissionState, MissionStatus
from src.yby_seed.daemon.mqtt_listener import MqttAutonomyWorker
from src.yby_seed.exporter.project_builder import export_validated_project
from src.yby_seed.exporter.serial_probe import scan_serial_devices_sync
from src.yby_seed.main import app
from src.yby_seed.memory import ledger
from src.yby_seed.models import StructuredCode


def _mission_embedded() -> MissionState:
    return MissionState(
        mission_id="m-esp",
        user_intent="led gpio quatro",
        domain="esp_idf",
        status=MissionStatus.SUCCESS,
        gpio_manifest={
            "pins": [{"gpio": 4, "role": "led_status", "notes": "ativo baixo"}],
            "board": "seeed_xiao_esp32s3",
        },
        generated_code=StructuredCode(
            language="cpp_embedded",
            filename="main.cpp",
            code='#include "pinout_manifest.h"\nvoid setup() {}\n',
        ),
    )


def _mission_python() -> MissionState:
    return MissionState(
        mission_id="m-py",
        user_intent="healthcheck api",
        domain="python_fastapi",
        status=MissionStatus.SUCCESS,
        generated_code=StructuredCode(
            language="python",
            filename="main.py",
            code="def ping():\n    return True\n",
            tests="def test_ping():\n    assert ping()\n",
        ),
    )


def test_platformio_and_pinout_generation(tmp_path: Path) -> None:
    folder, zip_name = export_validated_project(
        _mission_embedded(),
        "seeed_xiao_esp32s3",
        export_root=tmp_path,
    )
    ini = (folder / "platformio.ini").read_text(encoding="utf-8")
    assert "seeed_xiao_esp32s3" in ini
    assert "espidf" in ini
    pinout = (folder / "include" / "pinout_manifest.h").read_text(encoding="utf-8")
    assert "YBY_PIN_LED_STATUS 4" in pinout
    assert (tmp_path / zip_name).is_file()


def test_zip_packaging_contents(tmp_path: Path) -> None:
    _, zip_name = export_validated_project(
        _mission_python(),
        "esp32_s3_devkitc1",
        export_root=tmp_path,
    )
    archive = tmp_path / zip_name
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
    assert "main.py" in names
    assert "test_main.py" in names
    assert "pyproject.toml" in names


def test_serial_sysfs_simulation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sysfs = tmp_path / "sys" / "class" / "tty" / "ttyACM0" / "device"
    sysfs.mkdir(parents=True)
    (sysfs / "manufacturer").write_text("Espressif", encoding="utf-8")

    def fake_glob(pattern: str) -> list[str]:
        if pattern == "/dev/ttyACM*":
            return ["/dev/ttyACM0"]
        return []

    monkeypatch.setattr(
        "src.yby_seed.exporter.serial_probe._scan_pyserial",
        lambda: [],
    )
    monkeypatch.setattr("glob.glob", fake_glob)
    monkeypatch.setattr("os.path.exists", lambda p: True)
    monkeypatch.setattr("os.path.realpath", lambda p: p)

    devices = scan_serial_devices_sync()
    assert any(d.path.endswith("ttyACM0") for d in devices)


@pytest.mark.asyncio
async def test_ledger_record_and_economy_stats() -> None:
    ledger.reset_local_ledger_for_tests()
    state = _mission_python()
    await ledger.record_mission_completion(state, model_routed="yby-local", latency_ms=120)
    stats = await ledger.get_economy_stats()
    assert stats["total_missions"] >= 1
    assert stats["local_missions"] >= 1
    assert stats["budget_cap_usd"] == 3.5


def _enter_gateway_patches(stack: ExitStack) -> None:
    stack.enter_context(patch.object(MqttAutonomyWorker, "start", AsyncMock()))
    stack.enter_context(patch.object(MqttAutonomyWorker, "stop", AsyncMock()))
    stack.enter_context(
        patch("src.yby_seed.runtime.resources.open_pg_pool", new=AsyncMock(return_value=None))
    )


def test_hardware_ports_endpoint() -> None:
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "src.yby_seed.main.scan_serial_devices",
                new=AsyncMock(return_value=[]),
            )
        )
        _enter_gateway_patches(stack)
        with TestClient(app) as client:
            res = client.get("/v1/seed/hardware/ports")
    assert res.status_code == 200
    assert "devices" in res.json()


def test_export_endpoint_with_mission_payload(tmp_path: Path) -> None:
    mission = _mission_embedded().model_dump(mode="json")

    with ExitStack() as stack:
        _enter_gateway_patches(stack)
        stack.enter_context(
            patch(
                "src.yby_seed.exporter.project_builder.EXPORT_ROOT",
                tmp_path,
            )
        )
        stack.enter_context(
            patch(
                "src.yby_seed.main.EXPORT_ROOT",
                tmp_path,
            )
        )
        with TestClient(app) as client:
            res = client.post(
                "/v1/seed/export",
                json={"target_board": "seeed_xiao_esp32s3", "mission": mission},
            )
    assert res.status_code == 200
    body = res.json()
    assert body["archive_name"].endswith(".zip")
    assert (tmp_path / body["archive_name"]).is_file()

    with ExitStack() as stack:
        _enter_gateway_patches(stack)
        stack.enter_context(patch("src.yby_seed.main.EXPORT_ROOT", tmp_path))
        with TestClient(app) as client:
            blob = client.get(f"/v1/seed/export/{body['archive_name']}")
    assert blob.status_code == 200
    assert blob.headers["content-type"].startswith("application/zip")
    with zipfile.ZipFile(io.BytesIO(blob.content)) as zf:
        assert any(n.endswith("platformio.ini") for n in zf.namelist())


def test_stats_endpoint() -> None:
    with ExitStack() as stack:
        _enter_gateway_patches(stack)
        stack.enter_context(
            patch(
                "src.yby_seed.memory.ledger.get_economy_stats",
                AsyncMock(
                    return_value={
                        "total_missions": 2,
                        "local_missions": 2,
                        "cloud_missions": 0,
                        "local_pct": 100.0,
                        "cloud_pct": 0.0,
                        "estimated_savings_usd": 0.01,
                        "ledger_cloud_cost_usd": 0.0,
                        "monthly_spend_usd": 0.0,
                        "budget_cap_usd": 3.5,
                        "budget_remaining_usd": 3.5,
                        "validated_pairs": 0,
                        "gpu_profile": "GTX 1650 (local-first)",
                    }
                ),
            )
        )
        with TestClient(app) as client:
            res = client.get("/v1/seed/stats")
    assert res.status_code == 200
    assert res.json()["local_pct"] == 100.0
