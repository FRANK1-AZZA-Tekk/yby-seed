from fastapi.testclient import TestClient

from src.gateway.fastapi_mqtt_bridge import app, telemetry_queue


def test_invalid_telemetry_is_rejected_as_422():
    with TestClient(app) as client:
        response = client.post("/telemetry", json={"device_id": "", "timestamp": "not-a-date", "metrics": {}})
    assert response.status_code == 422


def test_valid_telemetry_is_acknowledged_as_memory_only():
    while not telemetry_queue.empty():
        telemetry_queue.get_nowait()
        telemetry_queue.task_done()
    payload = {"device_id": "watch-test", "timestamp": "2026-10-09T12:00:00Z", "metrics": {"steps": 5}}
    with TestClient(app) as client:
        response = client.post("/telemetry", json=payload)
    assert response.status_code == 202
    assert response.json()["persistence"] == "not_implemented"
    assert telemetry_queue.qsize() == 1
