import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.yby_seed.daemon.dataset_curator import curate_dataset
from src.yby_seed.daemon.mqtt_listener import MqttAutonomyWorker
from src.yby_seed.main import app
from src.yby_seed.telemetry import collect_telemetry


@pytest.fixture
def client() -> TestClient:
    with (
        patch.object(MqttAutonomyWorker, "start", AsyncMock()),
        patch.object(MqttAutonomyWorker, "stop", AsyncMock()),
    ):
        yield TestClient(app)


def test_home_and_forge(client: TestClient) -> None:
    assert client.get("/").status_code == 200
    with patch("src.yby_seed.main.vast_router.run_mission", return_value={"dry_run": True}):
        res = client.post("/v1/seed/forge/dry-run", json={"mission": "quantize"})
    assert res.status_code == 200


def test_telemetry_payload_shape(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.yby_seed.telemetry.read_gpu_stats",
        lambda: {"available": False, "vram_total_mb": 4096, "vram_used_mb": 0, "temperature_c": 0},
    )
    monkeypatch.setattr("src.yby_seed.telemetry.read_container_status", lambda: {"litellm": "up"})
    monkeypatch.setattr(
        "src.yby_seed.telemetry.read_openrouter_spend",
        lambda: {"spent_usd": 1.0, "budget_usd": 3.5, "remaining_usd": 2.5},
    )
    payload = collect_telemetry()
    assert payload["openrouter"]["budget_usd"] == 3.5
    assert "containers" in payload


def test_curator_chatml_validation(tmp_path: Path) -> None:
    path = tmp_path / "validated_pairs.jsonl"
    bad = {"messages": [{"role": "user", "content": "only user"}]}
    good = {
        "messages": [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
        ]
    }
    path.write_text(json.dumps(bad) + "\n" + json.dumps(good) + "\n", encoding="utf-8")
    report = curate_dataset(path)
    assert report.kept == 1
    assert report.removed_invalid == 1


@pytest.mark.asyncio
async def test_mqtt_respects_vram_queue() -> None:
    worker = MqttAutonomyWorker()
    worker._client = MagicMock()
    with patch(
        "src.yby_seed.daemon.mqtt_listener.check_gpu_headroom",
        return_value={"decision": "queue_or_fallback", "reason": "low"},
    ):
        await worker._handle_request("r99", {"prompt": "x"})
    assert worker._client.publish.call_args[0][0] == "yby/seed/response/r99"
