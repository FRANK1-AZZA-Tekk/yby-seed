"""Gateway FastAPI (yby_seed) — determinístico, sem Ollama/MQTT reais."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.yby_seed.daemon.mqtt_listener import MqttAutonomyWorker
from src.yby_seed.main import app
from src.yby_seed.models import GenerateResponse


def _enter_gateway_patches(stack: ExitStack) -> None:
    stack.enter_context(patch.object(MqttAutonomyWorker, "start", AsyncMock()))
    stack.enter_context(patch.object(MqttAutonomyWorker, "stop", AsyncMock()))
    stack.enter_context(
        patch("src.yby_seed.runtime.resources.open_pg_pool", new=AsyncMock(return_value=None))
    )


def test_health_routes_respond() -> None:
    with ExitStack() as stack:
        _enter_gateway_patches(stack)
        with TestClient(app) as client:
            home = client.get("/")
            assert home.status_code == 200
            assert "YBY" in home.text or "seed" in home.text.lower()


def test_generate_endpoint_accepts_payload() -> None:
    mock_response = GenerateResponse(
        success=True,
        attempts=1,
        code="def ping():\n    return True\n",
        filename="ping.py",
        language="python",
    )
    with ExitStack() as stack:
        _enter_gateway_patches(stack)
        stack.enter_context(
            patch(
                "src.yby_seed.engine.SeedEngine.generate",
                new=AsyncMock(return_value=mock_response),
            )
        )
        with TestClient(app) as client:
            response = client.post(
                "/v1/seed/generate",
                json={"prompt": "ping", "domain": "python_fastapi"},
            )
    assert response.status_code == 200
    assert response.json()["success"] is True
