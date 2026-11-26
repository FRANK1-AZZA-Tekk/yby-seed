"""Testes offline de integração ponta a ponta da Malha de 4 Nós do YBY SEED.

Cobre a conexão entre Baseus Bowie MC2 Air (`AsyncVoicePipeline`),
`TWatchBridge` (`map_audio_state_feedback`, `emit_machine_alert`, `sync_audio_state`),
assinante MQTT (`PahoMqttBridgeSubscriber`), gateway mobile no Xiaomi 12 (`/edge/sync`
e failover PocketPal :8080) e `yby_machine`, sem hardware LoRa.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.yby.app import build_mesh_app_from_env, create_mesh_app
from src.yby.audio import (
    TOPIC_AUDIO_STATE,
    TOPIC_TWATCH_CMD,
    TOPIC_TWATCH_TELEMETRY,
    TOPIC_TWATCH_VOICE,
    AsyncVoicePipeline,
    AudioPipelineConfig,
    BluetoothProfile,
    InMemoryMqttBus,
    PahoMqttBridgeSubscriber,
    TWatchBridge,
    map_audio_state_feedback,
)
from src.yby.edge_sync import EdgeSyncWorker, SQLiteFallbackEdgeStore
from src.yby.routing import CognitiveRouter, RouteTier, TierExecutionError
from src.yby_machine.http import create_app as create_machine_app
from src.yby_machine.pipeline import MachinePipeline
from src.yby_machine.spec import (
    ActionSpec,
    BrFieldType,
    EntitySpec,
    FieldSpec,
    PixConfig,
    WhatsAppConfig,
    YBYSpec,
)
from src.yby_machine.translator import TranslateResult


class FakeBaseusDevice:
    device_name = "Baseus Bowie MC2 Air"

    def __init__(self) -> None:
        self.profiles: list[BluetoothProfile] = []
        self.played: list[bytes] = []

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
        return b"RIFFfake"

    async def play_wav(self, wav_bytes: bytes) -> None:
        self.played.append(wav_bytes)


class FakeSTT:
    async def transcribe(self, wav_bytes: bytes, *, language: str = "pt") -> str:
        return "gerar cobranca Pix de R$ 45,00"


class FakeTTS:
    async def synthesize(self, text: str, *, voice: str = "pf_dora") -> bytes:
        return b"RIFFtts"


class HubAndPocketPalBackend:
    """Simula PC Hub (yby-fast) e failover no Xiaomi 12 (yby-mobile-fallback)."""

    def __init__(self, *, hub_online: bool = True) -> None:
        self.hub_online = hub_online
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
        if tier in {"yby-fast", "yby-code"} and not self.hub_online:
            raise TierExecutionError(tier, "Ollama local indisponível")
        if tier == "yby-mobile-fallback":
            return "Xiaomi 12 PocketPal: Pix R$ 45,00 pronto.", "qwen2.5-coder-3b-instruct"
        return "Hub: Pix R$ 45,00 gerado via wa.me.", "qwen2.5-coder:3b"


class FakePahoClient:
    def __init__(self) -> None:
        self.on_connect: Any = None
        self.on_message: Any = None
        self.subscriptions: list[tuple[str, int]] = []
        self.connected_to: tuple[str, int, int] | None = None
        self.loop_started = False
        self.stopped = False

    def subscribe(self, topic: str, qos: int = 0) -> None:
        self.subscriptions.append((topic, qos))

    def connect(self, host: str, port: int, keepalive: int = 60) -> None:
        self.connected_to = (host, port, keepalive)
        if self.on_connect is not None:
            self.on_connect(self, None, None, 0)

    def loop_start(self) -> None:
        self.loop_started = True

    def loop_stop(self) -> None:
        self.stopped = True

    def disconnect(self) -> None:
        return None


@pytest.mark.asyncio
async def test_audio_pipeline_syncs_twatch_bridge_feedback_and_colors() -> None:
    mqtt = InMemoryMqttBus()
    backend = HubAndPocketPalBackend(hub_online=True)
    router = CognitiveRouter(backend=backend)
    bridge = TWatchBridge(router=router, mqtt_bus=mqtt)
    device = FakeBaseusDevice()

    pipeline = AsyncVoicePipeline(
        device=device,
        stt=FakeSTT(),
        tts=FakeTTS(),
        router=router,
        mqtt_bus=mqtt,
        config=AudioPipelineConfig(),
        twatch_bridge=bridge,
    )

    result = await pipeline.run_turn()
    assert result.spoken is True
    assert result.route_tier == "yby-fast"
    assert device.profiles == ["hfp", "a2dp"]

    audio_states = [
        json.loads(m.payload)["state"] for m in mqtt.messages if m.topic == TOPIC_AUDIO_STATE
    ]
    assert audio_states == ["listening", "thinking", "speaking", "idle"]

    cmd_payloads = [
        json.loads(m.payload) for m in mqtt.messages if m.topic == TOPIC_TWATCH_CMD
    ]
    set_states = [c for c in cmd_payloads if c["command"] == "set_state"]
    assert [(c["state"], c["accent_color"]) for c in set_states] == [
        ("listening", map_audio_state_feedback("listening")[1]),
        ("thinking", map_audio_state_feedback("thinking")[1]),
        ("speaking", map_audio_state_feedback("speaking")[1]),
        ("idle", map_audio_state_feedback("idle")[1]),
    ]
    display_cmds = [c for c in cmd_payloads if c["command"] == "display_text"]
    assert len(display_cmds) == 1
    assert display_cmds[0]["accent_color"] == "#00FF66"


@pytest.mark.asyncio
async def test_mqtt_subscriber_dispatches_twatch_voice_with_pocketpal_failover() -> None:
    mqtt = InMemoryMqttBus()
    # Simula PC Hub offline -> failover automático para PocketPal AI no Xiaomi 12.
    backend = HubAndPocketPalBackend(hub_online=False)
    router = CognitiveRouter(backend=backend)
    bridge = TWatchBridge(router=router, mqtt_bus=mqtt)

    fake_paho = FakePahoClient()
    subscriber = PahoMqttBridgeSubscriber(
        handler=bridge.dispatch_mqtt_message,
        host="100.64.0.1",
        port=1883,
        client=fake_paho,
    )
    subscriber.start()
    assert fake_paho.connected_to == ("100.64.0.1", 1883, 60)
    assert (TOPIC_TWATCH_VOICE, 1) in fake_paho.subscriptions
    assert (TOPIC_TWATCH_TELEMETRY, 1) in fake_paho.subscriptions

    # Telemetria via callback MQTT
    tel_msg = SimpleNamespace(
        topic=TOPIC_TWATCH_TELEMETRY,
        payload=json.dumps(
            {
                "device_id": "twatch-s3-plus",
                "battery_pct": 79,
                "charging": False,
                "wifi_rssi": -58,
                "state": "idle",
            }
        ).encode("utf-8"),
    )
    fake_paho.on_message(fake_paho, None, tel_msg)
    await asyncio.sleep(0)
    assert bridge.latest_telemetry["twatch-s3-plus"].battery_pct == 79

    # Atalho de voz 2C (sem áudio bruto / sem LoRa)
    fut = subscriber.process_message(
        TOPIC_TWATCH_VOICE,
        json.dumps(
            {
                "device_id": "twatch-s3-plus",
                "transcript": "Status bateria e Pix",
                "audio_b64": None,
                "sensitivity": "private",
            }
        ),
    )
    reply = await fut
    assert reply is not None
    assert reply.tier == "yby-mobile-fallback"
    assert reply.metadata.privacy_blocked_cloud is True
    assert "PocketPal" in reply.text

    cmds = [json.loads(m.payload) for m in mqtt.messages if m.topic == TOPIC_TWATCH_CMD]
    assert cmds[-1]["command"] == "display_text"
    assert cmds[-1]["accent_color"] == "#00FF66"
    subscriber.stop()
    assert fake_paho.stopped is True


def test_mesh_app_integrates_xiaomi_edge_sync_twatch_and_yby_machine(
    tmp_path: Path,
) -> None:
    mqtt = InMemoryMqttBus()
    backend = HubAndPocketPalBackend(hub_online=True)
    router = CognitiveRouter(backend=backend)
    bridge = TWatchBridge(router=router, mqtt_bus=mqtt)
    store = SQLiteFallbackEdgeStore(tmp_path / "mesh_edge.sqlite3")
    edge_worker = EdgeSyncWorker(
        primary_store=store,
        mqtt_bus=mqtt,
        twatch_bridge=bridge,
    )
    audio = AsyncVoicePipeline(
        device=FakeBaseusDevice(),
        stt=FakeSTT(),
        tts=FakeTTS(),
        router=router,
        mqtt_bus=mqtt,
        twatch_bridge=bridge,
    )

    app = create_mesh_app(
        router=router,
        audio_pipeline=audio,
        edge_worker=edge_worker,
        twatch_bridge=bridge,
        expected_token="mesh-secret",
    )
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["modules"] == {
        "routing": True,
        "audio": True,
        "edge_sync": True,
        "twatch": True,
    }

    # Proteção fail-closed nas rotas T-Watch
    assert client.get("/twatch/telemetry").status_code == 401
    assert (
        client.post(
            "/twatch/voice",
            json={"device_id": "twatch-01", "transcript": "status"},
        ).status_code
        == 401
    )

    headers = {"Authorization": "Bearer mesh-secret"}

    # Xiaomi 12 envia lote via /edge/sync -> atualiza telemetria e dispara atalho 2C no TWatchBridge
    sync_resp = client.post(
        "/edge/sync",
        headers=headers,
        json={
            "source_node": "xiaomi12",
            "events": [
                {
                    "event_id": "x12-tel-1",
                    "device_id": "twatch-s3-plus",
                    "source_node": "xiaomi12",
                    "topic": TOPIC_TWATCH_TELEMETRY,
                    "payload": {"battery_pct": 85, "charging": True, "wifi_rssi": -61},
                },
                {
                    "event_id": "x12-voice-1",
                    "device_id": "twatch-s3-plus",
                    "source_node": "xiaomi12",
                    "topic": TOPIC_TWATCH_VOICE,
                    "payload": {"transcript": "resumo Pix R$ 120,00"},
                },
            ],
        },
    )
    assert sync_resp.status_code == 200
    assert sync_resp.json()["accepted"] == 2

    tel_resp = client.get("/twatch/telemetry", headers=headers)
    assert tel_resp.status_code == 200
    assert tel_resp.json()["twatch-s3-plus"]["battery_pct"] == 85

    voice_resp = client.post(
        "/twatch/voice",
        headers=headers,
        json={"device_id": "twatch-s3-plus", "transcript": "enviar resumo wa.me"},
    )
    assert voice_resp.status_code == 200
    assert voice_resp.json()["metadata"]["privacy_blocked_cloud"] is True

    empty_voice = client.post(
        "/twatch/voice",
        headers=headers,
        json={"device_id": "twatch-s3-plus", "transcript": "   "},
    )
    assert empty_voice.status_code == 422

    alert_resp = client.post(
        "/twatch/alert",
        headers=headers,
        json={
            "app_name": "PixFlow",
            "message": "Cobrança R$ 120,00 via wa.me pronta",
            "accent_color": "#00FF66",
        },
    )
    assert alert_resp.status_code == 200
    assert alert_resp.json()["command"] == "haptic_pulse"
    assert alert_resp.json()["accent_color"] == "#00FF66"


def test_yby_machine_generate_emits_alert_to_twatch_bridge() -> None:
    mqtt = InMemoryMqttBus()
    router = CognitiveRouter(backend=HubAndPocketPalBackend(hub_online=True))
    bridge = TWatchBridge(router=router, mqtt_bus=mqtt)

    async def fake_translator(_prompt: str) -> TranslateResult:
        spec = YBYSpec(
            name="CaixaPix",
            title="Caixa Pix",
            description="Fluxo Pix em R$ e wa.me",
            entities=[
                EntitySpec(
                    name="venda",
                    label="Venda",
                    fields=[
                        FieldSpec(
                            name="valor",
                            label="Valor (R$)",
                            type=BrFieldType.moeda_brl,
                        )
                    ],
                )
            ],
            actions=[
                ActionSpec(name="cobrar", label="Cobrar R$ 50"),
            ],
            pix=PixConfig(
                enabled=True,
                payload=(
                    "00020126360014BR.GOV.BCB.PIX0114+5511999999999"
                    "5204000053039865802BR5909YBY SEED6009SAO PAULO6304ABCD"
                ),
            ),
            whatsapp=WhatsAppConfig(enabled=True, phone_e164="+5511999999999"),
        )
        return TranslateResult(spec=spec, source="ollama")

    machine_app = create_machine_app(
        pipeline=MachinePipeline(translator=fake_translator),
        twatch_bridge=bridge,
    )
    client = TestClient(machine_app)
    resp = client.post("/api/machine/generate", json={"prompt": "app de cobranca Pix"})
    assert resp.status_code == 200

    alerts = [
        json.loads(m.payload)
        for m in mqtt.messages
        if m.topic == TOPIC_TWATCH_CMD and json.loads(m.payload)["command"] == "haptic_pulse"
    ]
    assert len(alerts) == 1
    assert alerts[0]["text"] == "[CaixaPix] App pronto (ollama)"
    assert alerts[0]["accent_color"] == "#00FF66"


def test_build_mesh_app_from_env_boots_offline_with_sqlite_fallback(tmp_path: Path) -> None:
    app = build_mesh_app_from_env(
        {
            "YBY_EDGE_SYNC_TOKEN": "env-token",
            "YBY_EDGE_FALLBACK_DB": str(tmp_path / "env_fallback.sqlite3"),
        },
        enable_mqtt_subscriber=False,
    )
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["modules"] == {
        "routing": True,
        "audio": True,
        "edge_sync": True,
        "twatch": True,
    }
