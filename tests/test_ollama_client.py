"""Robustez do OllamaClient legado (src/core)."""

from __future__ import annotations

import pytest
import requests

from src.core.ollama_client import OllamaClient, OllamaClientError


class _Resp:
    def __init__(self, status: int = 200, payload: dict | None = None) -> None:
        self.status_code = status
        self._payload = payload or {"response": "oi"}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"http {self.status_code}")


class _Session:
    def __init__(self, *, error: Exception | None = None, response: _Resp | None = None) -> None:
        self.error = error
        self.response = response or _Resp()
        self.closed = False

    def post(self, url: str, **kwargs: object) -> _Resp:
        if self.error:
            raise self.error
        return self.response

    def close(self) -> None:
        self.closed = True


def test_generate_raises_on_connection_error() -> None:
    client = OllamaClient()
    client.session = _Session(error=ConnectionError("down"))  # type: ignore[assignment]
    with pytest.raises(OllamaClientError, match="generate falhou"):
        client.generate("qwen2.5-coder:3b", "oi")


def test_generate_raises_on_ollama_error_field() -> None:
    client = OllamaClient()
    client.session = _Session(response=_Resp(200, {"error": "model missing"}))  # type: ignore[assignment]
    with pytest.raises(OllamaClientError, match="model missing"):
        client.generate("qwen2.5-coder:3b", "oi")


def test_close_shuts_session() -> None:
    client = OllamaClient()
    session = _Session()
    client.session = session  # type: ignore[assignment]
    client.close()
    assert session.closed is True