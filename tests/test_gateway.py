import asyncio

import pytest
from fastapi.testclient import TestClient

from src.gateway.fastapi_mqtt_bridge import app, telemetry_queue


@pytest.fixture(autouse=True)
def clear_telemetry_queue():
    while not telemetry_queue.empty():
        telemetry_queue.get_nowait()
        telemetry_queue.task_done()
    yield
    while not telemetry_queue.empty():
        telemetry_queue.get_nowait()
        telemetry_queue.task_done()


def test_invalid_telemetry_is_rejected_as_422():
    with TestClient(app) as client:
        response = client.post(
            "/telemetry",
            json={"device_id": "", "timestamp": "not-a-date", "metrics": {}},
        )
    assert response.status_code == 422


def test_valid_telemetry_is_acknowledged_as_memory_only():
    payload = {
        "device_id": "watch-test",
        "timestamp": "2026-10-09T12:00:00Z",
        "metrics": {"steps": 5},
    }
    with TestClient(app) as client:
        response = client.post("/telemetry", json=payload)
    assert response.status_code == 202
    assert response.json()["status"] == "queued_in_memory"
    assert response.json()["persistence"] == "not_implemented"
    assert telemetry_queue.qsize() == 1
    assert telemetry_queue.get_nowait()["device_id"] == "watch-test"
    telemetry_queue.task_done()


def test_full_queue_returns_503(monkeypatch):
    class FullQueue:
        def put_nowait(self, _item):
            raise asyncio.QueueFull

    monkeypatch.setattr("src.gateway.fastapi_mqtt_bridge.telemetry_queue", FullQueue())
    payload = {
        "device_id": "watch-test",
        "timestamp": "2026-10-09T12:00:00Z",
        "metrics": {},
    }
    with TestClient(app) as client:
        response = client.post("/telemetry", json=payload)
    assert response.status_code == 503
