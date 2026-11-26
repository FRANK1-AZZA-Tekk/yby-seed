"""Testes 100% offline do Módulo B (PipeWire Baseus, Whisper.cpp, Kokoro-82M e MQTT)."""

from __future__ import annotations

import asyncio
import json
import struct
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from src.yby.audio import (
    TOPIC_AUDIO_STATE,
    TOPIC_TWATCH_CMD,
    AsyncVoicePipeline,
    AudioBackendError,
    AudioPipelineConfig,
    BluetoothProfile,
    InMemoryMqttBus,
    KokoroTTSBackend,
    PipeWireBluetoothDevice,
    TWatchCommand,
    TWatchTelemetry,
    TWatchVoiceEnvelope,
    WhisperCppBackend,
    has_voice_activity,
)
from src.yby.routing import CognitiveRouter, RouteTier


class FakeCommandRunner:
    """Mock de subprocesso assíncrono para PipeWire, Whisper.cpp e Kokoro-82M."""

    def __init__(
        self,
        *,
        handler: Any = None,
    ) -> None:
        self.commands: list[list[str]] = []
        self._handler = handler

    async def run(
        self,
        argv: Sequence[str],
        *,
        stdin_bytes: bytes | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, bytes, bytes]:
        cmd = list(argv)
        self.commands.append(cmd)
        if self._handler is not None:
            return self._handler(cmd, stdin_bytes)
        return 0, b"", b""


class FakeBluetoothDevice:
    device_name = "Baseus Bowie MC2 Air"

    def __init__(self, *, capture_delay: float = 0.0, captured_wav: bytes = b"RIFFfake") -> None:
        self.profiles: list[BluetoothProfile] = []
        self.played: list[bytes] = []
        self._delay = capture_delay
        self._captured = captured_wav

    async def detect_device(self) -> str | None:
        return "bluez_card.Baseus_Bowie_MC2_Air"

    async def set_profile(self, profile: BluetoothProfile) -> bool:
        self.profiles.append(profile)
        return True

    async def record_utterance(
        self,
        *,
        max_seconds: float = 10.0,
        sample_rate: int = 16_000,
    ) -> bytes:
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        return self._captured

    async def play_wav(self, wav_bytes: bytes) -> None:
        self.played.append(wav_bytes)


class FakeSTT:
    def __init__(self, text: str = "Qual o status da bateria?", *, fail: bool = False) -> None:
        self._text = text
        self._fail = fail

    async def transcribe(self, wav_bytes: bytes, *, language: str = "pt") -> str:
        if self._fail:
            raise AudioBackendError("stt offline")
        return self._text


class FakeTTS:
    def __init__(self, wav: bytes = b"RIFFkokoro", *, fail: bool = False) -> None:
        self._wav = wav
        self._fail = fail

    async def synthesize(self, text: str, *, voice: str = "pf_dora") -> bytes:
        if self._fail:
            raise AudioBackendError("kokoro indisponivel")
        return self._wav


class RecordingLLMBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[RouteTier, str, dict[str, Any] | None]] = []

    async def complete(
        self,
        tier: RouteTier,
        prompt: str,
        *,
        system: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        self.calls.append((tier, prompt, metadata))
        return "Bateria em 88 por cento.", f"mock-{tier}"


@pytest.mark.asyncio
async def test_pipewire_detects_baseus_and_switches_hfp_a2dp() -> None:
    def handle(cmd: list[str], _stdin: bytes | None) -> tuple[int, bytes, bytes]:
        if cmd[:3] == ["pactl", "list", "cards"]:
            return (
                0,
                b"42\tbluez_card.AA_BB_CC_Baseus_Bowie_MC2_Air\tmodule-bluez5-device.c\n",
                b"",
            )
        if cmd[:2] == ["pactl", "set-card-profile"]:
            return 0, b"", b""
        return 0, b"", b""

    runner = FakeCommandRunner(handler=handle)
    device = PipeWireBluetoothDevice(runner=runner)

    card = await device.detect_device()
    assert card == "bluez_card.AA_BB_CC_Baseus_Bowie_MC2_Air"
    assert await device.set_profile("hfp") is True
    assert await device.set_profile("a2dp") is True

    assert runner.commands[1] == [
        "pactl",
        "set-card-profile",
        "bluez_card.AA_BB_CC_Baseus_Bowie_MC2_Air",
        "headset-head-unit",
    ]
    assert runner.commands[2] == [
        "pactl",
        "set-card-profile",
        "bluez_card.AA_BB_CC_Baseus_Bowie_MC2_Air",
        "a2dp-sink",
    ]


def test_vad_distinguishes_silence_from_speech() -> None:
    silence = struct.pack("<100h", *([0] * 100))
    speech = struct.pack("<100h", *([2000, -2000] * 50))
    assert has_voice_activity(silence) is False
    assert has_voice_activity(speech) is True


@pytest.mark.asyncio
async def test_whisper_cpp_and_kokoro_backends_with_mock_runner() -> None:
    def handle(cmd: list[str], stdin_bytes: bytes | None) -> tuple[int, bytes, bytes]:
        if cmd[0] == "whisper-cli":
            return 0, b"  abrir painel yby  \n", b""
        if cmd[0] == "kokoro-tts":
            out_idx = cmd.index("--output") + 1
            Path(cmd[out_idx]).write_bytes(b"RIFFWAVE" + (stdin_bytes or b""))
            return 0, b"", b""
        return 1, b"", b"unknown"

    runner = FakeCommandRunner(handler=handle)
    stt = WhisperCppBackend(model_path="/tmp/ggml-base.bin", runner=runner)
    tts = KokoroTTSBackend(runner=runner)

    text = await stt.transcribe(b"RIFFinput")
    assert text == "abrir painel yby"

    wav = await tts.synthesize("Olá YBY")
    assert wav.startswith(b"RIFFWAVE")

    with pytest.raises(AudioBackendError):
        await WhisperCppBackend(model_path="", runner=runner).transcribe(b"RIFFinput")


@pytest.mark.asyncio
async def test_voice_pipeline_publishes_mqtt_states_and_keeps_audio_private() -> None:
    device = FakeBluetoothDevice()
    mqtt = InMemoryMqttBus()
    llm_backend = RecordingLLMBackend()
    router = CognitiveRouter(backend=llm_backend)

    pipeline = AsyncVoicePipeline(
        device=device,
        stt=FakeSTT("Pesquisa web sobre minha agenda"),
        tts=FakeTTS(b"RIFFreply"),
        router=router,
        mqtt_bus=mqtt,
        config=AudioPipelineConfig(),
    )

    result = await pipeline.run_turn()

    assert result.spoken is True
    assert result.audio_bytes_out == len(b"RIFFreply")
    assert result.route_tier == "yby-fast"
    assert device.profiles == ["hfp", "a2dp"]
    assert device.played == [b"RIFFreply"]
    assert pipeline.state == "idle"

    # Áudio bruto nunca pode ir para a nuvem.
    assert len(llm_backend.calls) == 1
    tier, _, meta = llm_backend.calls[0]
    assert tier != "yby-cloud-frontier"
    assert meta is not None and meta["sensitivity"] == "private"
    assert meta["origin"] == "raw_audio"

    state_msgs = [m for m in mqtt.messages if m.topic == TOPIC_AUDIO_STATE]
    states = [json.loads(m.payload)["state"] for m in state_msgs]
    assert states == ["listening", "thinking", "speaking", "idle"]
    assert all(m.qos == 1 and m.retain is True for m in state_msgs)

    twatch_msgs = [m for m in mqtt.messages if m.topic == TOPIC_TWATCH_CMD]
    assert len(twatch_msgs) == 1
    twatch_payload = json.loads(twatch_msgs[0].payload)
    assert twatch_payload["accent_color"] == "#00FF66"


@pytest.mark.asyncio
async def test_voice_pipeline_is_non_blocking_and_recovers_to_idle_on_errors() -> None:
    device = FakeBluetoothDevice(capture_delay=0.05)
    mqtt = InMemoryMqttBus()
    router = CognitiveRouter(backend=RecordingLLMBackend())
    pipeline = AsyncVoicePipeline(
        device=device,
        stt=FakeSTT("status"),
        tts=FakeTTS(fail=True),
        router=router,
        mqtt_bus=mqtt,
    )

    task = pipeline.start_turn_background()

    # Uma tarefa concorrente deve concluir enquanto a captura de áudio aguarda.
    ticks = 0

    async def concurrent_work() -> None:
        nonlocal ticks
        for _ in range(3):
            await asyncio.sleep(0.005)
            ticks += 1

    await concurrent_work()
    assert ticks == 3

    turn = await task
    assert turn.spoken is False
    assert turn.error is not None
    assert pipeline.state == "idle"

    # Falha em STT também devolve o estado a `idle` via finally.
    failing_pipeline = AsyncVoicePipeline(
        device=FakeBluetoothDevice(),
        stt=FakeSTT(fail=True),
        tts=FakeTTS(),
        router=router,
        mqtt_bus=mqtt,
    )
    with pytest.raises(AudioBackendError):
        await failing_pipeline.run_turn()
    assert failing_pipeline.state == "idle"
    last_state = json.loads(
        [m for m in mqtt.messages if m.topic == TOPIC_AUDIO_STATE][-1].payload
    )["state"]
    assert last_state == "idle"


def test_twatch_mqtt_contract_schemas() -> None:
    telemetry = TWatchTelemetry(
        device_id="twatch-01",
        battery_pct=82,
        charging=False,
        wifi_rssi=-62,
    )
    cmd = TWatchCommand(command="display_text", text="YBY pronto", accent_color="#00FF66")
    voice = TWatchVoiceEnvelope(device_id="twatch-01", transcript="ligar modo foco")

    assert telemetry.battery_pct == 82
    assert cmd.accent_color == "#00FF66"
    assert voice.sensitivity == "private"
