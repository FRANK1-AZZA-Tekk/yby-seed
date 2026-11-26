"""Testes de integração Gateway (PR #118 + PR #119, LanceDB, embeddings e A09)."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

if "lancedb" not in sys.modules:
    sys.modules["lancedb"] = ModuleType("lancedb")
    sys.modules["lancedb"].connect = MagicMock()

from src.gateway import fastapi_mqtt_bridge as bridge  # noqa: E402
from src.gateway.config import Settings  # noqa: E402
from src.gateway.lancedb_client import LanceDBClient  # noqa: E402
from src.gateway.mqtt_listener import on_message  # noqa: E402


@pytest.mark.asyncio
async def test_paho_thread_to_worker_to_db_and_ws_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valida a combinação PR #119 (thread-safe MQTT) + PR #118 (await process_batch) + WS."""
    test_queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    ws_q: asyncio.Queue = asyncio.Queue(maxsize=10)
    monkeypatch.setattr(bridge, "mqtt_queue", test_queue)
    monkeypatch.setattr(bridge, "_ws_queues", {MagicMock(): ws_q})

    inserted: list[dict] = []

    class FakeDB:
        async def insert(self, data: dict) -> None:
            inserted.append(data)

    monkeypatch.setattr(bridge, "db_client", FakeDB())
    monkeypatch.setattr(bridge, "generate_embedding", lambda _features: [0.25] * 384)

    loop = asyncio.get_running_loop()
    userdata = {"queue": test_queue, "loop": loop}
    msg = MagicMock(
        topic="yby/telemetry",
        payload=json.dumps(
            {
                "device_id": "watch-combo-1",
                "timestamp": "2026-11-26T12:00:00Z",
                "metrics": {"heart_rate": 68, "battery": 85},
            }
        ).encode("utf-8"),
        qos=1,
    )

    worker_task = asyncio.create_task(bridge._telemetry_worker())
    try:
        thread = threading.Thread(target=lambda: on_message(MagicMock(), userdata, msg))
        thread.start()
        thread.join(timeout=2.0)

        ws_item = await asyncio.wait_for(ws_q.get(), timeout=3.0)
        assert ws_item["device_id"] == "watch-combo-1"
        await asyncio.wait_for(test_queue.join(), timeout=3.0)
        assert len(inserted) == 1
        assert inserted[0]["device_id"] == "watch-combo-1"
        assert len(inserted[0]["vector"]) == 384
    finally:
        worker_task.cancel()
        await asyncio.gather(worker_task, return_exceptions=True)


def test_vectors_search_embeds_query_and_handles_ollama_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge, "settings", Settings(GATEWAY_TOKEN="tok-gw"))
    fake_db = MagicMock()
    fake_db.search = AsyncMock(return_value=[{"id": "1", "text": "hr=72"}])
    monkeypatch.setattr(bridge, "db_client", fake_db)

    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {"embedding": [0.1] * 384}

    client = TestClient(bridge.app)
    headers = {"Authorization": "Bearer tok-gw"}

    with patch("src.gateway.fastapi_mqtt_bridge.httpx.post", return_value=fake_resp) as post_mock:
        res = client.post("/vectors/search", params={"query": "batimentos altos", "top_k": 3}, headers=headers)
        assert res.status_code == 200
        body = res.json()
        assert body["query"] == "batimentos altos"
        assert body["results"] == [{"id": "1", "text": "hr=72"}]
        post_mock.assert_called_once()
        fake_db.search.assert_awaited_once()
        passed_vec = fake_db.search.await_args.args[0]
        assert isinstance(passed_vec, list)
        assert len(passed_vec) == 384

    # Query vazia / top_k inválido
    assert client.post("/vectors/search", params={"query": "   "}, headers=headers).status_code == 400
    assert client.post("/vectors/search", params={"query": "ok", "top_k": 0}, headers=headers).status_code == 400

    # Ollama indisponível -> 503
    with patch("src.gateway.fastapi_mqtt_bridge.httpx.post", side_effect=httpx.ConnectError("down")):
        down = client.post("/vectors/search", params={"query": "sono"}, headers=headers)
        assert down.status_code == 503


def test_gateway_sanitizes_internal_errors_and_validates_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge, "settings", Settings(GATEWAY_TOKEN="tok-gw"))
    fake_db = MagicMock()
    fake_db.get_metrics = AsyncMock(side_effect=RuntimeError("db password=secret_leak"))
    fake_db.search = AsyncMock(side_effect=RuntimeError("internal stack trace leak"))
    monkeypatch.setattr(bridge, "db_client", fake_db)

    client = TestClient(bridge.app)
    headers = {"Authorization": "Bearer tok-gw"}

    assert client.get("/metrics", params={"device_id": "  "}, headers=headers).status_code == 400
    assert client.get("/metrics", params={"device_id": "w1", "limit": 5000}, headers=headers).status_code == 400

    res_metrics = client.get("/metrics", params={"device_id": "w1"}, headers=headers)
    assert res_metrics.status_code == 500
    assert "secret_leak" not in res_metrics.json()["detail"]

    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {"embedding": [0.2] * 384}
    with patch("src.gateway.fastapi_mqtt_bridge.httpx.post", return_value=fake_resp):
        res_search = client.post("/vectors/search", params={"query": "teste"}, headers=headers)
        assert res_search.status_code == 500
        assert "stack trace leak" not in res_search.json()["detail"]


def test_generate_embedding_fallback_is_normalized_and_non_zero() -> None:
    with patch("src.gateway.fastapi_mqtt_bridge.httpx.post", side_effect=httpx.ConnectError("offline")):
        vec = bridge.generate_embedding({"heart_rate_avg": 75})
    assert len(vec) == 384
    assert any(v != 0.0 for v in vec)
    norm_sq = sum(v * v for v in vec)
    assert abs(norm_sq - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_lancedb_client_lazy_connect_and_table_compact() -> None:
    with patch("src.gateway.lancedb_client.lancedb.connect") as connect_mock:
        ldb = LanceDBClient("/tmp/lazy-lance-path")
        connect_mock.assert_not_called()

        fake_db = MagicMock()
        fake_db.table_names.return_value = ["metrics", "vectors"]
        metrics_tbl = MagicMock()
        vectors_tbl = MagicMock()
        fake_db.open_table.side_effect = [metrics_tbl, vectors_tbl]
        connect_mock.return_value = fake_db

        await ldb.init_tables()
        connect_mock.assert_called_once()

        await ldb.compact()
        metrics_tbl.compact_files.assert_called_once()
        vectors_tbl.compact_files.assert_called_once()
