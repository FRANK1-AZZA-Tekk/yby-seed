import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.yby_seed.daemon.dataset_curator import curate_dataset
from src.yby_seed.daemon.mqtt_listener import MqttAutonomyWorker
from src.yby_seed.main import app
from src.yby_seed.mcp.server import build_mcp_server
from src.yby_seed.memory.chunking import iter_semantic_chunks
from src.yby_seed.telemetry import collect_telemetry, count_validated_pairs


def test_homepage() -> None:
    with patch.object(MqttAutonomyWorker, "start", AsyncMock()), patch.object(
        MqttAutonomyWorker, "stop", AsyncMock()
    ):
        client = TestClient(app)
        response = client.get("/")
    assert response.status_code == 200
    assert "YBY SEED" in response.text


def test_forge_dry_run_endpoint() -> None:
    with patch.object(MqttAutonomyWorker, "start", AsyncMock()), patch.object(
        MqttAutonomyWorker, "stop", AsyncMock()
    ), patch("src.yby_seed.main.vast_router.run_mission", return_value={"dry_run": True}):
        client = TestClient(app)
        response = client.post("/v1/seed/forge/dry-run", json={"mission": "quantize"})
    assert response.status_code == 200
    assert response.json()["dry_run"] is True


def test_telemetry_collect(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.yby_seed.telemetry.read_gpu_stats",
        lambda: {"available": False, "vram_total_mb": 4096, "vram_used_mb": 0, "temperature_c": 0},
    )
    monkeypatch.setattr("src.yby_seed.telemetry.read_container_status", lambda: {"postgres": "down"})
    monkeypatch.setattr(
        "src.yby_seed.telemetry.read_openrouter_spend",
        lambda: {"spent_usd": 0.0, "budget_usd": 3.5, "remaining_usd": 3.5},
    )
    payload = collect_telemetry()
    assert payload["validated_pairs"] == count_validated_pairs()


def test_dataset_curator_dedup(tmp_path: Path) -> None:
    target = tmp_path / "validated_pairs.jsonl"
    row = {"messages": [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]}
    target.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
    report = curate_dataset(target)
    assert report.kept == 1
    assert report.removed_duplicate == 1


def test_chunking_preserves_code_fence() -> None:
    text = "Intro\n\n```python\nprint(1)\n```\n"
    chunks = list(iter_semantic_chunks(text))
    assert any("```python" in c for c in chunks)


def test_mcp_server_tools() -> None:
    server = build_mcp_server()
    names = {t.name for t in server._tool_manager.list_tools()}  # noqa: SLF001
    assert "check_gpu_headroom" in names


@pytest.mark.asyncio
async def test_mqtt_worker_queues_on_low_vram() -> None:
    worker = MqttAutonomyWorker()
    worker._client = MagicMock()
    with patch("src.yby_seed.daemon.mqtt_listener.check_gpu_headroom", return_value={"decision": "queue_or_fallback", "reason": "low"}):
        await worker._handle_request("r1", {"prompt": "teste", "domain": "python_fastapi"})
    worker._client.publish.assert_called()
    topic = worker._client.publish.call_args[0][0]
    assert topic == "yby/seed/response/r1"
