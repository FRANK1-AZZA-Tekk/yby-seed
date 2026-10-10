from fastapi.testclient import TestClient

from src.gateway.fastapi_mqtt_bridge import app, mqtt_queue


def test_invalid_telemetry_is_rejected_as_422():
    with TestClient(app) as client:
        response = client.post("/telemetry", json={"device_id": "", "timestamp": "not-a-date", "metrics": {}})
    assert response.status_code == 422


def test_telemetry_is_queued_and_worker_does_not_consume_for_websocket():
    with TestClient(app) as client:
        response = client.post("/telemetry", json={"device_id": "watch-1", "timestamp": "2026-10-09T12:00:00Z", "metrics": {"steps": 5}})
        assert response.status_code == 202
        assert response.json()["status"] == "queued"
