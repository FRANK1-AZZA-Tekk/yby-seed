"""Testes de autenticação, validação, timeout e limpeza do servidor FUSION (A05)."""

from __future__ import annotations

import base64
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.vision.fusion import server as fusion_server


def _valid_chat_payload() -> dict:
    b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode("ascii")
    return {
        "model": "yby-vision",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "O que há na foto?"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }
        ],
    }


def test_fusion_server_health_open_and_completions_fail_closed_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FUSION_API_TOKEN", raising=False)
    monkeypatch.delenv("GATEWAY_TOKEN", raising=False)
    fake_client = MagicMock()
    app = fusion_server.create_app(client=fake_client)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        resp = client.post("/v1/chat/completions", json=_valid_chat_payload())
        assert resp.status_code == 503
        fake_client.analyze.assert_not_called()


def test_fusion_server_rejects_invalid_token_and_accepts_bearer_or_x_api_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FUSION_API_TOKEN", "fusion-secret-123")
    observed_paths: list[Path] = []

    def _analyze(path: Path, prompt: str) -> str:
        observed_paths.append(path)
        assert path.exists()
        assert "foto" in prompt
        return "Uma mesa de madeira."

    fake_client = MagicMock()
    fake_client.analyze.side_effect = _analyze
    app = fusion_server.create_app(client=fake_client)

    with TestClient(app) as client:
        bad = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer wrong"},
            json=_valid_chat_payload(),
        )
        assert bad.status_code == 401

        ok_bearer = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer fusion-secret-123"},
            json=_valid_chat_payload(),
        )
        assert ok_bearer.status_code == 200
        assert ok_bearer.json()["choices"][0]["message"]["content"] == "Uma mesa de madeira."

        ok_header = client.post(
            "/v1/chat/completions",
            headers={"X-API-Token": "fusion-secret-123"},
            json=_valid_chat_payload(),
        )
        assert ok_header.status_code == 200

    assert len(observed_paths) == 2
    assert all(not p.exists() for p in observed_paths)


def test_fusion_server_sanitizes_errors_and_enforces_timeout() -> None:
    fake_client = MagicMock()
    app = fusion_server.create_app(client=fake_client, api_token="tok")

    with TestClient(app) as client:
        bad_json = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer tok"},
            content="{invalid",
        )
        assert bad_json.status_code == 400
        assert bad_json.json()["detail"] == "Payload JSON inválido."

        bad_b64 = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer tok"},
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,!!!"}}],
                    }
                ]
            },
        )
        assert bad_b64.status_code == 400
        assert bad_b64.json()["detail"] == "image_url base64 inválido."

        fake_client.analyze.side_effect = FileNotFoundError("/tmp/secret_temp_path.png")
        missing = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer tok"},
            json=_valid_chat_payload(),
        )
        assert missing.status_code == 404
        assert "/tmp/secret_temp_path.png" not in missing.json()["detail"]

    slow_client = MagicMock()
    slow_client.analyze.side_effect = lambda *_args: time.sleep(0.2) or "ok"
    timeout_app = fusion_server.create_app(client=slow_client, inference_timeout_s=0.02, api_token="tok")
    with TestClient(timeout_app) as client:
        timed_out = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer tok"},
            json=_valid_chat_payload(),
        )
        assert timed_out.status_code == 504


def test_fusion_main_refuses_non_loopback_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUSION_SERVER_HOST", "0.0.0.0")
    monkeypatch.delenv("FUSION_API_TOKEN", raising=False)
    monkeypatch.delenv("GATEWAY_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="FUSION_API_TOKEN"):
        fusion_server.main()
