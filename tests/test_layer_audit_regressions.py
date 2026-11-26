"""Testes de regressão da auditoria camada por camada (Layers 0-4)."""

from __future__ import annotations

import asyncio
import gc
import importlib
import logging
import subprocess
import sys
import types
import warnings
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from scripts.hil_qa_4nodes import HilQaConfig
from scripts.validate_skills import SkillValidator
from src.platform.hub import setup_logging
from src.yby.app import build_mesh_app_from_env, create_mesh_app
from src.yby.audio.device import PipeWireBluetoothDevice
from src.yby.audio.mqtt_bus import PahoMqttBridgeSubscriber
from src.yby.audio.service import AsyncVoicePipeline, AudioPipelineConfig
from src.yby.edge_sync.schemas import EdgeEvent
from src.yby.edge_sync.store import SQLiteFallbackEdgeStore
from src.yby.edge_sync.worker import OllamaEmbeddingProvider
from src.yby.routing.cache import InMemoryCacheBackend, build_cache_key
from src.yby.routing.privacy_gate import PrivacyGate
from src.yby.routing.router import CognitiveRouter, OpenAICompatibleBackend, RouterConfig
from src.yby.routing.schemas import RouteRequest, RouteResponse
from src.yby_machine.store_pgvector import PgVectorSpecStore, create_spec_store_from_env

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Layer 0: Scripts & Skills
# ---------------------------------------------------------------------------


def test_validate_skills_all_pass_with_zero_errors() -> None:
    validator = SkillValidator(str(REPO_ROOT / "skills"))
    assert validator.validate_all() is True
    assert validator.errors == []
    assert len(validator.successes) >= 6


# ---------------------------------------------------------------------------
# Layer 1: Core Platform & GPU Offload
# ---------------------------------------------------------------------------


def test_hub_setup_logging_closes_previous_file_handlers(tmp_path: Path) -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            setup_logging(log_path=tmp_path / "run1.log")
            setup_logging(log_path=tmp_path / "run2.log")
            for handler in list(root.handlers):
                root.removeHandler(handler)
                handler.close()
            gc.collect()
        resource_warnings = [w for w in caught if issubclass(w.category, ResourceWarning)]
        assert resource_warnings == []
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
            handler.close()
        for handler in original_handlers:
            root.addHandler(handler)


def test_gpu_offload_import_is_lazy_without_spawning_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def fail_subprocess(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        raise AssertionError("subprocess.run não deve rodar no import de gpu_offload")

    monkeypatch.setattr(subprocess, "run", fail_subprocess)
    sys.modules.pop("src.core.gpu_offload", None)
    mod = importlib.import_module("src.core.gpu_offload")
    assert calls == []
    assert hasattr(mod, "get_gpu_offload")


# ---------------------------------------------------------------------------
# Layer 2: Routing, PrivacyGate, Cache, HTTP Pool, Audio, MQTT, EdgeSync, App
# ---------------------------------------------------------------------------


def test_privacy_gate_blocks_sensitive_data_in_system_prompt() -> None:
    gate = PrivacyGate()
    req = RouteRequest(
        prompt="Resuma o plano arquitetural de hoje.",
        system_prompt="Contexto interno: chave Pix CPF 123.456.789-00",
        sensitivity="public",
    )
    decision = gate.evaluate(req)
    assert decision.allow_cloud is False
    assert decision.effective_sensitivity == "private"
    assert decision.redaction_count >= 1
    assert any("system_prompt" in reason for reason in decision.blocked_reasons)


def test_cache_key_isolates_system_prompt_and_preserves_legacy_key() -> None:
    key_none = build_cache_key("private", "yby-fast", "status")
    key_empty = build_cache_key("private", "yby-fast", "status", system_prompt="")
    key_watch = build_cache_key(
        "private",
        "yby-fast",
        "status",
        system_prompt="Responda em 1 frase curta para T-Watch.",
    )
    key_machine = build_cache_key(
        "private",
        "yby-fast",
        "status",
        system_prompt="Retorne JSON estrito para YBY Machine.",
    )
    assert key_none == key_empty
    assert key_watch != key_none
    assert key_watch != key_machine


@pytest.mark.asyncio
async def test_in_memory_cache_enforces_max_entries_and_prunes_expired() -> None:
    now = [100.0]
    cache = InMemoryCacheBackend(clock=lambda: now[0], max_entries=2)
    await cache.set("k1", '{"a": 1}', ttl_seconds=5)
    await cache.set("k2", '{"a": 2}', ttl_seconds=60)
    now[0] = 110.0  # k1 expirou
    await cache.set("k3", '{"a": 3}', ttl_seconds=60)
    assert await cache.get("k1") is None
    assert await cache.get("k2") == '{"a": 2}'
    assert await cache.get("k3") == '{"a": 3}'

    # Sem expirados, remove o mais antigo (k2)
    await cache.set("k4", '{"a": 4}', ttl_seconds=60)
    assert await cache.get("k2") is None
    assert await cache.get("k3") == '{"a": 3}'
    assert await cache.get("k4") == '{"a": 4}'


def test_router_config_from_env_reads_request_timeout() -> None:
    cfg = RouterConfig.from_env({"YBY_REQUEST_TIMEOUT_SECONDS": "12.5"})
    assert cfg.request_timeout_seconds == 12.5


@pytest.mark.asyncio
async def test_openai_compatible_backend_reuses_and_closes_http_client() -> None:
    backend = OpenAICompatibleBackend(RouterConfig())
    c1 = backend._get_client()
    c2 = backend._get_client()
    assert c1 is c2
    assert not c1.is_closed
    await backend.aclose()
    assert c1.is_closed


@pytest.mark.asyncio
async def test_ollama_embedding_provider_reuses_and_closes_http_client() -> None:
    provider = OllamaEmbeddingProvider(ollama_host="http://127.0.0.1:11434")
    c1 = provider._get_client()
    c2 = provider._get_client()
    assert c1 is c2
    assert not c1.is_closed
    await provider.aclose()
    assert c1.is_closed


@pytest.mark.asyncio
async def test_sqlite_fallback_store_closes_connections_without_resource_warning(
    tmp_path: Path,
) -> None:
    store = SQLiteFallbackEdgeStore(tmp_path / "edge.sqlite3")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        await store.ensure_schema()
        event = EdgeEvent(
            event_id="evt-close-check",
            device_id="xiaomi-12",
            source_node="xiaomi_12",
            topic="yby/twatch/telemetry",
            payload={"battery_pct": 90},
            text_summary="bateria 90%",
        )
        assert await store.upsert_event(event, [1.0, 0.0]) == "inserted"
        assert await store.count_events() == 1
        assert await store.count_pending() == 1
        hits = await store.search_similar([1.0, 0.0], limit=3)
        assert len(hits) == 1
        gc.collect()

    resource_warnings = [w for w in caught if issubclass(w.category, ResourceWarning)]
    assert resource_warnings == []


@pytest.mark.asyncio
async def test_bluetooth_set_profile_invalidates_stale_card_and_retries() -> None:
    class FlakyRunner:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []
            self._list_count = 0

        async def run(
            self,
            argv: list[str],
            *,
            stdin_bytes: bytes | None = None,
            timeout: float = 15.0,
        ) -> tuple[int, bytes, bytes]:
            self.calls.append(list(argv))
            if list(argv[:4]) == ["pactl", "list", "cards", "short"]:
                self._list_count += 1
                card_name = (
                    "bluez_card.baseus_old"
                    if self._list_count == 1
                    else "bluez_card.baseus_new"
                )
                stdout = f"42\t{card_name}\tmodule-bluez5-device.c\n"
                return (0, stdout.encode("utf-8"), b"")
            if list(argv[:3]) == ["pactl", "set-card-profile", "bluez_card.baseus_old"]:
                return (1, b"", b"No such entity")
            if list(argv[:3]) == ["pactl", "set-card-profile", "bluez_card.baseus_new"]:
                return (0, b"", b"")
            return (1, b"", b"unexpected")

    runner = FlakyRunner()
    device = PipeWireBluetoothDevice(runner=runner)
    first_card = await device.detect_device()
    assert first_card == "bluez_card.baseus_old"

    ok = await device.set_profile("hfp")
    assert ok is True
    assert device._cached_card == "bluez_card.baseus_new"


@pytest.mark.asyncio
async def test_mqtt_subscriber_tracks_tasks_and_logs_async_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def broken_handler(topic: str, payload: bytes | str) -> None:
        raise RuntimeError(f"boom on {topic}: {payload!r}")

    sub = PahoMqttBridgeSubscriber(
        handler=broken_handler,
        topics=("yby/test",),
        loop=asyncio.get_running_loop(),
    )

    with caplog.at_level(logging.WARNING, logger="yby.audio.mqtt_bus"):
        sub.process_message("yby/test", b"hello")
        await asyncio.sleep(0.05)

    assert "Falha assíncrona no handler MQTT" in caplog.text
    assert len(sub._pending_tasks) == 0


@pytest.mark.asyncio
async def test_voice_pipeline_background_task_logs_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class BrokenDevice:
        async def detect_device(self) -> str | None:
            return "bluez_card.TEST"

        async def set_profile(self, profile: str) -> bool:
            return True

        async def record_utterance(
            self,
            *,
            max_seconds: float = 10.0,
            sample_rate: int = 16000,
        ) -> bytes:
            raise RuntimeError("mic offline")

        async def play_wav(self, wav_bytes: bytes) -> None:
            return None

    class DummyStt:
        async def transcribe(self, wav_bytes: bytes, *, language: str = "pt") -> str:
            return ""

    class DummyTts:
        async def synthesize(self, text: str, *, voice: str | None = None) -> bytes:
            return b""

    class DummyRouter:
        async def route(self, request: RouteRequest) -> RouteResponse:
            raise AssertionError("não deveria chamar router")

    pipeline = AsyncVoicePipeline(
        device=BrokenDevice(),  # type: ignore[arg-type]
        stt=DummyStt(),  # type: ignore[arg-type]
        tts=DummyTts(),  # type: ignore[arg-type]
        router=DummyRouter(),  # type: ignore[arg-type]
        config=AudioPipelineConfig(max_record_seconds=0.5),
    )

    with caplog.at_level(logging.WARNING, logger="yby.audio.service"):
        task = pipeline.start_turn_background()
        with pytest.raises(RuntimeError, match="mic offline"):
            await task
        await asyncio.sleep(0)

    assert "Turno de voz em background falhou" in caplog.text


def test_build_mesh_app_from_env_honors_env_example_vars_and_closes_router(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "custom_edge.sqlite3"
    app = build_mesh_app_from_env(
        {
            "YBY_EDGE_SQLITE_PATH": str(db_file),
            "YBY_WHISPER_CPP_BIN": "/opt/bin/whisper-custom",
            "YBY_KOKORO_BIN": "/opt/bin/kokoro-custom",
            "YBY_MQTT_SUBSCRIBE_ENABLED": "0",
        }
    )
    assert app.state.audio_pipeline.stt.binary == "/opt/bin/whisper-custom"
    assert app.state.audio_pipeline.tts.binary == "/opt/bin/kokoro-custom"
    assert app.state.edge_worker.primary_store.path == db_file

    # Verifica que router.aclose() é invocado no shutdown do lifespan
    mock_router = CognitiveRouter(
        config=RouterConfig(),
        backend=OpenAICompatibleBackend(
            RouterConfig(),
            http_client=httpx.AsyncClient(),
        ),
    )
    mock_router.aclose = AsyncMock()  # type: ignore[method-assign]
    minimal_app = create_mesh_app(router=mock_router)
    with TestClient(minimal_app) as client:
        assert client.get("/health").status_code == 200
    mock_router.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# Layer 3: YBY Machine & HIL QA
# ---------------------------------------------------------------------------


def test_machine_store_accepts_yby_pgvector_dsn_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "psycopg", types.ModuleType("psycopg"))
    store = create_spec_store_from_env({"YBY_PGVECTOR_DSN": "postgresql://u:p@localhost/yby"})
    assert isinstance(store, PgVectorSpecStore)
    assert store.dsn == "postgresql://u:p@localhost/yby"


def test_hil_qa_config_parses_mqtt_credentials() -> None:
    cfg = HilQaConfig.from_env(
        {
            "YBY_MQTT_HOST": "10.0.0.5",
            "YBY_MQTT_PORT": "1884",
            "YBY_MQTT_USER": "yby_node",
            "YBY_MQTT_PASS": "secret_pass",
        }
    )
    assert cfg.mqtt_host == "10.0.0.5"
    assert cfg.mqtt_port == 1884
    assert cfg.mqtt_user == "yby_node"
    assert cfg.mqtt_pass == "secret_pass"


# ---------------------------------------------------------------------------
# Layer 4: Firmware T-Watch S3 Plus static contract checks
# ---------------------------------------------------------------------------


def test_twatch_firmware_contracts_for_state_backlight_and_deepsleep() -> None:
    fw_src = REPO_ROOT / "firmware" / "twatch_s3_plus" / "src"
    mqtt_cpp = (fw_src / "mqtt_mesh.cpp").read_text(encoding="utf-8")
    main_cpp = (fw_src / "main.cpp").read_text(encoding="utf-8")
    pmu_cpp = (fw_src / "power_pmu.cpp").read_text(encoding="utf-8")

    # 1. set_state propaga doc["state"] e dispara haptics
    assert 'doc["state"]' in mqtt_cpp
    assert 'strcmp(cmd, "set_state") == 0' in main_cpp
    assert "g_haptics.playAudioState(g_audio_state);" in main_cpp

    # 2. setBacklight não desliga ALDO2 (evita tela corrompida ao acordar de light-sleep)
    set_bl_start = pmu_cpp.index("void PowerPmuManager::setBacklight")
    set_bl_end = pmu_cpp.index("void PowerPmuManager::notifyInteraction")
    set_bl_body = pmu_cpp[set_bl_start:set_bl_end]
    assert "disableALDO2" not in set_bl_body

    # 3. enterDeepSleep desliga ALDO2 e não usa ESP_EXT1_WAKEUP_ALL_LOW
    deep_start = pmu_cpp.index("void PowerPmuManager::enterDeepSleep")
    deep_body = pmu_cpp[deep_start:]
    assert "s_pmu.disableALDO2();" in deep_body
    assert "ESP_EXT1_WAKEUP_ALL_LOW" not in pmu_cpp
