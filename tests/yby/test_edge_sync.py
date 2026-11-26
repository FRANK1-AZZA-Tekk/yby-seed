"""Testes 100% offline do Módulo D (Edge Sync Xiaomi 12, pgvector mock, SQLite WAL e FastAPI)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.yby.app import create_mesh_app
from src.yby.audio import AsyncVoicePipeline, InMemoryMqttBus
from src.yby.edge_sync import (
    EdgeEvent,
    EdgeSyncBatchRequest,
    EdgeSyncWorker,
    PgVectorEdgeStore,
    SQLiteFallbackEdgeStore,
)
from src.yby.routing import CognitiveRouter, RouteTier


class FakeAsyncCursor:
    """Cursor psycopg em memória para validar SQL e idempotência do PgVectorEdgeStore."""

    def __init__(self, rows_store: dict[str, dict[str, Any]], executed: list[str]) -> None:
        self._store = rows_store
        self._executed = executed
        self._last_one: tuple[Any, ...] | None = None
        self._last_all: list[tuple[Any, ...]] = []

    async def __aenter__(self) -> FakeAsyncCursor:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        self._executed.append(" ".join(sql.split()))
        self._last_one = None
        self._last_all = []
        upper = sql.upper()
        if "INSERT INTO YBY_EDGE_EVENTS" in upper and params is not None:
            event_id = str(params[0])
            if event_id not in self._store:
                self._store[event_id] = {
                    "event_id": event_id,
                    "device_id": params[1],
                    "source_node": params[2],
                    "topic": params[3],
                    "payload": json.loads(params[4]),
                    "text_summary": params[5],
                    "captured_at": params[6],
                    "sensitivity": params[7],
                    "embedding": params[8],
                }
                self._last_one = (event_id,)
            else:
                self._last_one = None
        elif "SELECT COUNT(*)" in upper:
            self._last_one = (len(self._store),)
        elif "ORDER BY EMBEDDING <=>" in upper:
            for item in list(self._store.values()):
                self._last_all.append(
                    (
                        item["event_id"],
                        item["device_id"],
                        item["source_node"],
                        item["topic"],
                        item["payload"],
                        item["captured_at"],
                        item["sensitivity"],
                        0.97,
                    )
                )

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self._last_one

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return self._last_all


class FakeAsyncPgConnection:
    def __init__(self, rows_store: dict[str, dict[str, Any]], executed: list[str]) -> None:
        self._store = rows_store
        self._executed = executed
        self.committed = False
        self.closed = False

    def cursor(self) -> FakeAsyncCursor:
        return FakeAsyncCursor(self._store, self._executed)

    async def commit(self) -> None:
        self.committed = True

    async def close(self) -> None:
        self.closed = True


class FlakyPrimaryStore:
    """Simula queda temporária e recuperação do Postgres para testar fallback SQLite."""

    backend_name = "pgvector"

    def __init__(self, *, online: bool = True) -> None:
        self.online = online
        self.events: dict[str, tuple[EdgeEvent, list[float] | None]] = {}

    async def ensure_schema(self) -> None:
        if not self.online:
            raise ConnectionError("postgres down")

    async def upsert_event(
        self,
        event: EdgeEvent,
        embedding: list[float] | None,
    ) -> str:
        if not self.online:
            raise ConnectionError("postgres down")
        if event.event_id in self.events:
            return "duplicate"
        self.events[event.event_id] = (event, embedding)
        return "inserted"

    async def count_events(self) -> int:
        if not self.online:
            raise ConnectionError("postgres down")
        return len(self.events)

    async def search_similar(self, query_embedding: list[float], *, limit: int = 5) -> list[Any]:
        return []


class StaticEmbedder:
    async def embed(self, text: str) -> list[float] | None:
        base = float((len(text) % 10) + 1)
        return [base, 0.5, 0.25]


class DummyRouterBackend:
    async def complete(
        self,
        tier: RouteTier,
        prompt: str,
        *,
        system: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        return f"ok:{prompt}", f"mock-{tier}"


class DummyAudioDevice:
    device_name = "Baseus Bowie MC2 Air"

    async def detect_device(self) -> str | None:
        return "bluez_card.Baseus"

    async def set_profile(self, profile: Any) -> bool:
        return True

    async def record_utterance(
        self,
        *,
        max_seconds: float = 10.0,
        sample_rate: int = 16_000,
    ) -> bytes:
        return b"RIFFtest"

    async def play_wav(self, wav_bytes: bytes) -> None:
        return None


class DummySTT:
    async def transcribe(self, wav_bytes: bytes, *, language: str = "pt") -> str:
        return "oi"


class DummyTTS:
    async def synthesize(self, text: str, *, voice: str = "pf_dora") -> bytes:
        return b"RIFFout"


@pytest.mark.asyncio
async def test_pgvector_store_schema_idempotency_and_search() -> None:
    rows: dict[str, dict[str, Any]] = {}
    executed: list[str] = []

    async def factory() -> FakeAsyncPgConnection:
        return FakeAsyncPgConnection(rows, executed)

    store = PgVectorEdgeStore(dsn="postgresql://local/test", connection_factory=factory)
    await store.ensure_schema()
    assert any("CREATE EXTENSION IF NOT EXISTS vector" in sql for sql in executed)
    assert any("CREATE TABLE IF NOT EXISTS yby_edge_events" in sql for sql in executed)

    event = EdgeEvent(
        event_id="evt-001",
        device_id="twatch-s3-plus",
        topic="yby/nodes/twatch/telemetry",
        payload={"battery": 91},
        text_summary="telemetria bateria 91",
    )
    assert await store.upsert_event(event, [0.1, 0.2, 0.3]) == "inserted"
    assert await store.upsert_event(event, [0.1, 0.2, 0.3]) == "duplicate"
    assert await store.count_events() == 1

    hits = await store.search_similar([0.1, 0.2, 0.3], limit=3)
    assert len(hits) == 1
    assert hits[0].event_id == "evt-001"
    assert hits[0].score == pytest.approx(0.97)


@pytest.mark.asyncio
async def test_sqlite_fallback_store_and_drain_to_primary(tmp_path: Path) -> None:
    primary = FlakyPrimaryStore(online=False)
    fallback = SQLiteFallbackEdgeStore(tmp_path / "fallback.sqlite3")
    mqtt = InMemoryMqttBus()

    worker = EdgeSyncWorker(
        primary_store=primary,  # type: ignore[arg-type]
        fallback_store=fallback,
        embedder=StaticEmbedder(),
        mqtt_bus=mqtt,
    )

    batch = EdgeSyncBatchRequest(
        events=[
            EdgeEvent(
                event_id="evt-off-1",
                device_id="twatch-s3",
                topic="yby/nodes/twatch/telemetry",
                payload={"battery": 75},
                text_summary="bateria 75",
            ),
            EdgeEvent(
                event_id="evt-off-2",
                device_id="xiaomi12",
                topic="yby/nodes/twatch/telemetry",
                payload={"battery": 74},
                text_summary="bateria 74",
                sync_origin="hub_republished",
            ),
        ]
    )

    # Com Postgres offline, eventos caem no SQLite WAL sem perda.
    res = await worker.ingest_batch(batch)
    assert res.accepted == 2
    assert res.duplicates == 0
    assert res.store_backend == "sqlite_fallback"
    assert await fallback.count_pending() == 2

    # Apenas evt-off-1 deve ser republicado (evt-off-2 já tem sync_origin="hub_republished").
    assert len(mqtt.messages) == 1
    assert json.loads(mqtt.messages[0].payload)["event_id"] == "evt-off-1"

    # Busca por similaridade funciona também offline no fallback SQLite.
    similar = await fallback.search_similar([1.0, 0.5, 0.25], limit=2)
    assert len(similar) == 2

    # Postgres volta online -> dreno idempotente move eventos e zera fila pendente.
    primary.online = True
    drain_result = await worker.drain_fallback()
    assert drain_result == {"inserted": 2, "duplicates": 0, "remaining": 0}
    assert await primary.count_events() == 2

    # Dreno repetido não duplica.
    drain_again = await worker.drain_fallback()
    assert drain_again == {"inserted": 0, "duplicates": 0, "remaining": 0}


def test_edge_sync_fastapi_auth_idempotency_and_mesh_app(tmp_path: Path) -> None:
    primary = FlakyPrimaryStore(online=True)
    fallback = SQLiteFallbackEdgeStore(tmp_path / "api_fallback.sqlite3")
    worker = EdgeSyncWorker(
        primary_store=primary,  # type: ignore[arg-type]
        fallback_store=fallback,
        embedder=StaticEmbedder(),
        mqtt_bus=InMemoryMqttBus(),
    )
    router = CognitiveRouter(backend=DummyRouterBackend())
    audio = AsyncVoicePipeline(
        device=DummyAudioDevice(),
        stt=DummySTT(),
        tts=DummyTTS(),
        router=router,
        mqtt_bus=InMemoryMqttBus(),
    )

    # Sem token configurado -> 503 fail-closed
    app_no_token = create_mesh_app(edge_worker=worker, expected_token="")
    client_no_token = TestClient(app_no_token)
    assert client_no_token.get("/edge/health").status_code == 200
    resp_503 = client_no_token.post(
        "/edge/sync",
        json={
            "source_node": "xiaomi12",
            "events": [
                {
                    "event_id": "evt-503",
                    "device_id": "twatch",
                    "topic": "yby/nodes/twatch/telemetry",
                    "payload": {"battery": 50},
                }
            ],
        },
    )
    assert resp_503.status_code == 503

    # Com token configurado -> 401 sem header / 200 com Bearer ou X-API-Token
    app = create_mesh_app(
        router=router,
        audio_pipeline=audio,
        edge_worker=worker,
        expected_token="secret-mesh-token",
    )
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/audio/state").json() == {"state": "idle"}

    payload = {
        "source_node": "xiaomi12",
        "events": [
            {
                "event_id": "evt-sync-1",
                "device_id": "twatch-s3-plus",
                "topic": "yby/nodes/twatch/telemetry",
                "payload": {"battery": 88},
            },
            {
                "event_id": "evt-sync-2",
                "device_id": "xiaomi12",
                "topic": "yby/nodes/twatch/voice",
                "payload": {"transcript": "status"},
            },
        ],
    }

    assert client.post("/edge/sync", json=payload).status_code == 401

    headers = {"Authorization": "Bearer secret-mesh-token"}
    first = client.post("/edge/sync", json=payload, headers=headers)
    assert first.status_code == 200
    assert first.json()["accepted"] == 2
    assert first.json()["duplicates"] == 0

    # Reconexão Tailscale reenvia o mesmo lote -> 100% idempotente
    second = client.post("/edge/sync", json=payload, headers={"X-API-Token": "secret-mesh-token"})
    assert second.status_code == 200
    assert second.json()["accepted"] == 0
    assert second.json()["duplicates"] == 2

    status_resp = client.get("/edge/sync/status", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["total_stored"] == 2
    assert status_resp.json()["healthy"] is True

    # Endpoint `/route` e `/audio/turn` (202 não-bloqueante)
    route_resp = client.post(
        "/route",
        json={"prompt": "status", "sensitivity": "private"},
        headers=headers,
    )
    assert route_resp.status_code == 200
    assert route_resp.json()["tier"] == "yby-fast"

    turn_resp = client.post("/audio/turn", headers=headers)
    assert turn_resp.status_code == 202
    assert turn_resp.json()["status"] == "accepted"
