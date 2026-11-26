"""App FastAPI modular da Malha de 4 Nós (Módulos A, B, C-Bridge e D)."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from src.gateway.auth import check_token
from src.yby.audio.backends import KokoroTTSBackend, WhisperCppBackend
from src.yby.audio.device import PipeWireBluetoothDevice
from src.yby.audio.mqtt_bus import (
    InMemoryMqttBus,
    MqttPublisher,
    PahoMqttBridgeSubscriber,
    PahoMqttPublisher,
)
from src.yby.audio.schemas import (
    TOPIC_TWATCH_TELEMETRY,
    TOPIC_TWATCH_VOICE,
    TWatchCommand,
    TWatchVoiceEnvelope,
)
from src.yby.audio.service import AsyncVoicePipeline, AudioPipelineConfig
from src.yby.audio.twatch_bridge import AccentHex, TWatchBridge
from src.yby.edge_sync.api import create_edge_sync_router
from src.yby.edge_sync.store import (
    PgVectorEdgeStore,
    SQLiteFallbackEdgeStore,
    VectorEventStore,
)
from src.yby.edge_sync.worker import EdgeSyncWorker, OllamaEmbeddingProvider
from src.yby.routing.router import (
    CognitiveRouter,
    OpenAICompatibleBackend,
    RouterConfig,
    RoutingExhaustedError,
)
from src.yby.routing.schemas import RouteRequest, RouteResponse

logger = logging.getLogger("yby.app")


class TWatchAlertRequest(BaseModel):
    """Payload HTTP para emitir alerta háptico/visual no T-Watch S3 Plus (5A)."""

    model_config = ConfigDict(extra="forbid")

    app_name: str = Field(default="YBY", max_length=40)
    message: str = Field(..., min_length=1, max_length=160)
    accent_color: AccentHex = "#00FF66"


def _resolve_gateway_token(
    expected_token: str | None,
    environ: Mapping[str, str] | None = None,
) -> str:
    if expected_token is not None:
        return expected_token.strip()
    source = environ if environ is not None else os.environ
    return (
        source.get("YBY_EDGE_SYNC_TOKEN")
        or source.get("GATEWAY_TOKEN")
        or ""
    ).strip()


def create_mesh_app(
    *,
    router: CognitiveRouter | None = None,
    audio_pipeline: AsyncVoicePipeline | None = None,
    edge_worker: EdgeSyncWorker | None = None,
    twatch_bridge: TWatchBridge | None = None,
    expected_token: str | None = None,
    mqtt_subscriber: PahoMqttBridgeSubscriber | None = None,
    mqtt_publisher: MqttPublisher | None = None,
) -> FastAPI:
    """Fábrica testável do servidor HTTP da malha (não altera o gateway legado)."""

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if mqtt_subscriber is not None:
            try:
                mqtt_subscriber.start(loop=asyncio.get_running_loop())
            except Exception as exc:  # noqa: BLE001
                logger.warning("Falha ao iniciar subscriber MQTT do T-Watch: %s", exc)
        try:
            yield
        finally:
            if mqtt_subscriber is not None:
                try:
                    mqtt_subscriber.stop()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Falha ao parar subscriber MQTT: %s", exc)
            close_fn = getattr(mqtt_publisher, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Falha ao fechar publisher MQTT: %s", exc)
            if router is not None:
                router_close = getattr(router, "aclose", None)
                if callable(router_close):
                    try:
                        await router_close()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Falha ao fechar HTTP client do router: %s", exc)
            embedder = getattr(edge_worker, "embedder", None)
            embedder_close = getattr(embedder, "aclose", None)
            if callable(embedder_close):
                try:
                    await embedder_close()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Falha ao fechar HTTP client do embedder: %s", exc)

    app = FastAPI(
        title="YBY Mesh Hub (4-Node Local-First)",
        version="0.3.0",
        lifespan=lifespan,
    )
    app.state.router = router
    app.state.audio_pipeline = audio_pipeline
    app.state.edge_worker = edge_worker
    app.state.twatch_bridge = twatch_bridge

    def _guard(request: Request) -> None:
        ok, code, detail = check_token(
            request.headers,
            _resolve_gateway_token(expected_token),
        )
        if not ok:
            raise HTTPException(status_code=code, detail=detail)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "modules": {
                "routing": router is not None,
                "audio": audio_pipeline is not None,
                "edge_sync": edge_worker is not None,
                "twatch": twatch_bridge is not None,
            },
            "audio_state": audio_pipeline.state if audio_pipeline is not None else "disabled",
            "twatch_devices": (
                sorted(twatch_bridge.latest_telemetry.keys())
                if twatch_bridge is not None
                else []
            ),
        }

    if router is not None:

        @app.post("/route", response_model=RouteResponse)
        async def route_endpoint(body: RouteRequest, request: Request) -> RouteResponse:
            _guard(request)
            try:
                return await router.route(body)
            except RoutingExhaustedError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(exc),
                ) from exc

    if audio_pipeline is not None:

        @app.get("/audio/state")
        async def audio_state() -> dict[str, str]:
            return {"state": audio_pipeline.state}

        @app.post("/audio/turn", status_code=status.HTTP_202_ACCEPTED)
        async def trigger_audio_turn(request: Request) -> dict[str, str]:
            _guard(request)
            audio_pipeline.start_turn_background()
            return {"status": "accepted", "state": audio_pipeline.state}

    if twatch_bridge is not None:

        @app.get("/twatch/telemetry")
        async def twatch_telemetry(request: Request) -> dict[str, Any]:
            _guard(request)
            return {
                device_id: telemetry.model_dump()
                for device_id, telemetry in twatch_bridge.latest_telemetry.items()
            }

        @app.post("/twatch/voice", response_model=RouteResponse)
        async def twatch_voice(
            envelope: TWatchVoiceEnvelope,
            request: Request,
        ) -> RouteResponse:
            _guard(request)
            safe_envelope = envelope.model_copy(update={"sensitivity": "private"})
            try:
                reply = await twatch_bridge.handle_voice_message(
                    safe_envelope.model_dump_json()
                )
            except RoutingExhaustedError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(exc),
                ) from exc
            if reply is None:
                raise HTTPException(
                    status_code=422,
                    detail="transcript vazio ou envelope T-Watch inválido",
                )
            return reply

        @app.post("/twatch/alert", response_model=TWatchCommand)
        async def twatch_alert(
            body: TWatchAlertRequest,
            request: Request,
        ) -> TWatchCommand:
            _guard(request)
            return await twatch_bridge.emit_machine_alert(
                body.app_name,
                body.message,
                accent_color=body.accent_color,
            )

    if edge_worker is not None:
        app.include_router(
            create_edge_sync_router(edge_worker, expected_token=expected_token)
        )

    return app


def build_mesh_app_from_env(
    environ: Mapping[str, str] | None = None,
    *,
    enable_mqtt_subscriber: bool = True,
) -> FastAPI:
    """Instancia a malha completa (Módulos A, B, C-Bridge e D) a partir do ambiente."""

    source = environ if environ is not None else os.environ
    router_cfg = RouterConfig.from_env(source)
    router = CognitiveRouter(
        backend=OpenAICompatibleBackend(router_cfg),
        config=router_cfg,
    )

    mqtt_host = source.get("YBY_MQTT_HOST", "").strip()
    mqtt_port_raw = source.get("YBY_MQTT_PORT", "1883").strip()
    try:
        mqtt_port = int(mqtt_port_raw) if mqtt_port_raw else 1883
    except ValueError as exc:
        raise ValueError(f"YBY_MQTT_PORT inválido: {mqtt_port_raw!r}") from exc

    mqtt_user = source.get("YBY_MQTT_USER", "").strip() or None
    mqtt_pass = source.get("YBY_MQTT_PASS", "").strip() or None

    mqtt_bus: MqttPublisher
    if mqtt_host:
        mqtt_bus = PahoMqttPublisher(
            host=mqtt_host,
            port=mqtt_port,
            username=mqtt_user,
            password=mqtt_pass,
        )
    else:
        mqtt_bus = InMemoryMqttBus()

    twatch_bridge = TWatchBridge(router=router, mqtt_bus=mqtt_bus)

    audio_cfg = AudioPipelineConfig.from_env(source)
    whisper_bin = source.get("YBY_WHISPER_CPP_BIN", "whisper-cli").strip() or "whisper-cli"
    kokoro_bin = source.get("YBY_KOKORO_BIN", "kokoro-tts").strip() or "kokoro-tts"
    audio_pipeline = AsyncVoicePipeline(
        device=PipeWireBluetoothDevice(device_name=audio_cfg.bt_device_name),
        stt=WhisperCppBackend(
            binary=whisper_bin,
            model_path=source.get("YBY_WHISPER_CPP_MODEL", "").strip(),
        ),
        tts=KokoroTTSBackend(
            binary=kokoro_bin,
            default_voice=audio_cfg.kokoro_voice,
        ),
        router=router,
        mqtt_bus=mqtt_bus,
        config=audio_cfg,
        twatch_bridge=twatch_bridge,
    )

    fallback_raw = (
        source.get("YBY_EDGE_FALLBACK_DB")
        or source.get("YBY_EDGE_SQLITE_PATH")
        or "logs/edge_sync_fallback.sqlite3"
    ).strip()
    fallback_path = Path(fallback_raw or "logs/edge_sync_fallback.sqlite3")
    fallback_store = SQLiteFallbackEdgeStore(fallback_path)
    pg_dsn = (
        source.get("YBY_PGVECTOR_DSN")
        or source.get("YBY_DATABASE_URL")
        or source.get("DATABASE_URL")
        or ""
    ).strip()
    primary_store: VectorEventStore = (
        PgVectorEdgeStore(dsn=pg_dsn) if pg_dsn else fallback_store
    )

    ollama_embed_host = (
        source.get("YBY_OLLAMA_BASE_URL")
        or source.get("OLLAMA_API_BASE")
        or "http://127.0.0.1:11434"
    ).strip()
    embedder = OllamaEmbeddingProvider(ollama_host=ollama_embed_host)
    edge_worker = EdgeSyncWorker(
        primary_store=primary_store,
        fallback_store=fallback_store if pg_dsn else None,
        embedder=embedder,
        mqtt_bus=mqtt_bus,
        twatch_bridge=twatch_bridge,
    )

    subscriber: PahoMqttBridgeSubscriber | None = None
    if mqtt_host and enable_mqtt_subscriber:
        subscriber = PahoMqttBridgeSubscriber(
            handler=twatch_bridge.dispatch_mqtt_message,
            host=mqtt_host,
            port=mqtt_port,
            topics=(TOPIC_TWATCH_VOICE, TOPIC_TWATCH_TELEMETRY),
            username=mqtt_user,
            password=mqtt_pass,
        )

    return create_mesh_app(
        router=router,
        audio_pipeline=audio_pipeline,
        edge_worker=edge_worker,
        twatch_bridge=twatch_bridge,
        expected_token=_resolve_gateway_token(None, source),
        mqtt_subscriber=subscriber,
        mqtt_publisher=mqtt_bus,
    )
