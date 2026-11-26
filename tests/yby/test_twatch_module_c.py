"""Testes 100% offline do Módulo C (T-Watch S3 Plus sem LoRa: 1A, 2C, 3A, 4A, 5A, 6A)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from src.yby.audio import (
    TOPIC_TWATCH_CMD,
    TOPIC_TWATCH_TELEMETRY,
    TOPIC_TWATCH_VOICE,
    InMemoryMqttBus,
    TWatchCommand,
    TWatchTelemetry,
    TWatchVoiceEnvelope,
)
from src.yby.audio.twatch_bridge import TWatchBridge, map_audio_state_feedback
from src.yby.routing import CognitiveRouter, RouteTier

REPO_ROOT = Path(__file__).resolve().parents[2]
FIRMWARE_DIR = REPO_ROOT / "firmware" / "twatch_s3_plus"


class DummyLocalLLM:
    """Backend LLM offline para validar que atalhos 2C nunca vão à nuvem."""

    def __init__(self) -> None:
        self.calls: list[tuple[RouteTier, str]] = []

    async def complete(
        self,
        tier: RouteTier,
        prompt: str,
        *,
        system: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> tuple[str, str]:
        del system, metadata
        self.calls.append((tier, prompt))
        return f"Hub OK: {prompt[:40]}", f"mock-{tier}"


@pytest.mark.asyncio
async def test_twatch_bridge_routes_2c_shortcut_privately_and_replies_on_cmd() -> None:
    llm = DummyLocalLLM()
    router = CognitiveRouter(backend=llm)
    bus = InMemoryMqttBus()
    bridge = TWatchBridge(router=router, mqtt_bus=bus)

    envelope = TWatchVoiceEnvelope(
        device_id="twatch-s3-plus-01",
        transcript="Status da malha",
        audio_b64=None,
        sensitivity="private",
    )
    reply = await bridge.handle_voice_message(envelope.model_dump_json())
    assert reply is not None
    assert reply.metadata.privacy_blocked_cloud is True
    assert all(tier != "yby-cloud-frontier" for tier, _ in llm.calls)

    assert len(bus.messages) == 1
    published = bus.messages[0]
    assert published.topic == TOPIC_TWATCH_CMD
    cmd = TWatchCommand.model_validate_json(published.payload)
    assert cmd.command == "display_text"
    assert cmd.accent_color == "#00FF66"
    assert "Status da malha" in cmd.text


@pytest.mark.asyncio
async def test_twatch_bridge_rejects_empty_or_invalid_voice_envelope() -> None:
    router = CognitiveRouter(backend=DummyLocalLLM())
    bus = InMemoryMqttBus()
    bridge = TWatchBridge(router=router, mqtt_bus=bus)

    assert await bridge.handle_voice_message("{json-quebrado") is None
    empty = TWatchVoiceEnvelope(device_id="twatch-s3-plus-01", transcript="   ", audio_b64=None)
    assert await bridge.handle_voice_message(empty.model_dump_json()) is None
    assert bus.messages == []


@pytest.mark.asyncio
async def test_twatch_bridge_stores_telemetry_and_emits_5a_machine_alert() -> None:
    router = CognitiveRouter(backend=DummyLocalLLM())
    bus = InMemoryMqttBus()
    bridge = TWatchBridge(router=router, mqtt_bus=bus)

    tel = TWatchTelemetry(
        device_id="twatch-s3-plus-01",
        battery_pct=84,
        charging=False,
        wifi_rssi=-58,
        state="idle",
    )
    parsed = bridge.handle_telemetry_message(tel.model_dump_json())
    assert parsed is not None
    assert bridge.latest_telemetry["twatch-s3-plus-01"].battery_pct == 84
    assert TOPIC_TWATCH_TELEMETRY == "yby/nodes/twatch/telemetry"
    assert TOPIC_TWATCH_VOICE == "yby/nodes/twatch/voice"

    await bridge.emit_machine_alert("AgendaPix", "Novo PWA compilado e pronto no hub: " + ("x" * 200))
    assert len(bus.messages) == 1
    cmd = TWatchCommand.model_validate_json(bus.messages[0].payload)
    assert cmd.command == "haptic_pulse"
    assert cmd.accent_color == "#00FF66"
    assert cmd.text.startswith("[AgendaPix] ")
    assert len(cmd.text) <= 160


def test_5a_audio_state_haptic_and_color_mapping() -> None:
    assert map_audio_state_feedback("listening") == ("short_pulse", "#00FF66")
    assert map_audio_state_feedback("thinking") == ("micro_tick", "#F5F5F2")
    assert map_audio_state_feedback("speaking") == ("solid_arc", "#F5F5F2")
    assert map_audio_state_feedback("idle") == ("none", "#0D0D0D")


def test_6a_twatch_backup_creates_sha256_and_flash_enforces_backup_gate(
    tmp_path: Path,
) -> None:
    from scripts.twatch.backup import run_backup, verify_backup_sha256
    from scripts.twatch.build import run_build
    from scripts.twatch.flash import run_flash

    calls: list[list[str]] = []

    def fake_runner(cmd: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        # Simula saída do read_flash criando o arquivo binário alvo (último argumento)
        if "read_flash" in cmd:
            Path(cmd[-1]).write_bytes(b"\xE9YBY_FLASH_16MB")
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    # Sem backup, flash sem --skip-backup deve recusar (D10)
    with pytest.raises(RuntimeError, match="backup"):
        run_flash(
            firmware_dir=FIRMWARE_DIR,
            backup_dir=tmp_path,
            port="/dev/ttyACM0",
            skip_backup=False,
            runner=fake_runner,
        )

    # Backup grava binário + .sha256 válido
    bin_path, sha_path = run_backup(
        backup_dir=tmp_path,
        port="/dev/ttyACM0",
        runner=fake_runner,
    )
    assert bin_path.is_file()
    assert sha_path.is_file()
    expected_digest = hashlib.sha256(bin_path.read_bytes()).hexdigest()
    assert expected_digest in sha_path.read_text(encoding="utf-8")
    assert verify_backup_sha256(bin_path, sha_path) is True
    assert any("read_flash" in cmd and "0x1000000" in cmd for cmd in calls)

    # Agora o flash é autorizado pelo gate de backup
    rc_flash = run_flash(
        firmware_dir=FIRMWARE_DIR,
        backup_dir=tmp_path,
        port="/dev/ttyACM0",
        skip_backup=False,
        runner=fake_runner,
    )
    assert rc_flash == 0
    assert any("upload" in cmd for cmd in calls)

    # E build dispara pio run no diretório do firmware
    rc_build = run_build(firmware_dir=FIRMWARE_DIR, runner=fake_runner)
    assert rc_build == 0
    assert any("pio" in cmd[0] or "platformio" in cmd[0] for cmd in calls)

    # Com --skip-backup explícito em pasta vazia também funciona
    empty_dir = tmp_path / "sem_backup"
    empty_dir.mkdir()
    assert (
        run_flash(
            firmware_dir=FIRMWARE_DIR,
            backup_dir=empty_dir,
            port="/dev/ttyACM0",
            skip_backup=True,
            runner=fake_runner,
        )
        == 0
    )


def test_firmware_structure_and_hardware_choices_without_lora() -> None:
    pio_ini = (FIRMWARE_DIR / "platformio.ini").read_text(encoding="utf-8")
    assert "esp32-s3" in pio_ini.lower()
    assert "lvgl" in pio_ini.lower()
    assert "xpowerslib" in pio_ini.lower()
    assert "drv2605" in pio_ini.lower()
    assert "pubsubclient" in pio_ini.lower()
    assert "arduinojson" in pio_ini.lower()
    # MVP estritamente sem LoRa
    for forbidden in ("radiolib", "sx1262", "sx1280", "lora"):
        assert forbidden not in pio_ini.lower()

    cfg_h = (FIRMWARE_DIR / "include" / "yby_config.h").read_text(encoding="utf-8")
    # Pinout validado T-Watch S3 Plus + escolhas 1A/2C/3A/4A/5A
    for token in (
        "YBY_ENABLE_LORA 0",
        "YBY_ENABLE_BLE 0",
        "YBY_ENABLE_MIC 0",
        "YBY_I2C_SDA 10",
        "YBY_I2C_SCL 11",
        "YBY_TOUCH_SDA 39",
        "YBY_TOUCH_SCL 40",
        "YBY_TOUCH_INT 16",
        "YBY_PMU_INT 21",
        "YBY_BMA_INT 14",
        "YBY_DISP_BL 45",
        "YBY_LIGHT_SLEEP_MS 10000",
        "YBY_DEEP_SLEEP_MS 300000",
        "0x0D0D0D",
        "0xF5F5F2",
        "0x00FF66",
    ):
        assert token in cfg_h

    pmu_cpp = (FIRMWARE_DIR / "src" / "power_pmu.cpp").read_text(encoding="utf-8")
    assert "disableALDO4" in pmu_cpp
    assert "disableBLDO1" in pmu_cpp
    assert "100" in pmu_cpp or "125" in pmu_cpp or "130" in pmu_cpp

    for topic in (
        "yby/audio/state",
        "yby/nodes/twatch/telemetry",
        "yby/nodes/twatch/cmd",
        "yby/nodes/twatch/voice",
    ):
        assert topic in cfg_h

    mqtt_cpp = (FIRMWARE_DIR / "src" / "mqtt_mesh.cpp").read_text(encoding="utf-8")
    assert "YBY_TOPIC_AUDIO_STATE" in mqtt_cpp
    assert "YBY_TOPIC_TELEMETRY" in mqtt_cpp
    assert "YBY_TOPIC_CMD" in mqtt_cpp
    assert "YBY_TOPIC_VOICE" in mqtt_cpp
    assert "WIFI_PS_MIN_MODEM" in mqtt_cpp
    assert "failover" in mqtt_cpp.lower()

    ui_cpp = (FIRMWARE_DIR / "src" / "ui_lvgl.cpp").read_text(encoding="utf-8")
    assert "lv_tileview" in ui_cpp

    haptics_cpp = (FIRMWARE_DIR / "src" / "haptics.cpp").read_text(encoding="utf-8")
    assert "listening" in haptics_cpp
    assert "thinking" in haptics_cpp
    assert "speaking" in haptics_cpp
    assert "haptic_pulse" in haptics_cpp

    # Sanity: JSON example no secrets.example.h
    secrets_ex = (FIRMWARE_DIR / "include" / "secrets.example.h").read_text(encoding="utf-8")
    assert "YBY_WIFI_PRIMARY_SSID" in secrets_ex
    assert "YBY_WIFI_FAILOVER_SSID" in secrets_ex
    assert json.dumps("yby")  # garante json importado usado sem lint warning
