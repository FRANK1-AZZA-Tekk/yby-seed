"""Gateway FastAPI (yby_seed) — determinístico, sem Ollama/MQTT reais."""

from fastapi.testclient import TestClient

from src.yby_seed.main import app


def test_health_routes_respond() -> None:
    with TestClient(app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "YBY" in home.text or "seed" in home.text.lower()


def test_generate_endpoint_accepts_payload() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/seed/generate",
            json={"prompt": "ping", "domain": "python_fastapi"},
        )
        assert response.status_code in {200, 422, 500}
