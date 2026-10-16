from unittest.mock import Mock

import pytest
import requests

from src.core.ollama_client import (
    OllamaClient,
    OllamaHTTPError,
    OllamaProtocolError,
    OllamaTimeoutError,
    OllamaTransportError,
)


def _client_with(monkeypatch, post):
    client = OllamaClient(timeout=(3.0, 180.0))
    monkeypatch.setattr(client.session, "request", post)
    return client


def test_generate_sends_configured_timeout_and_payload(monkeypatch):
    post = Mock()
    post.return_value.json.return_value = {"response": "ok"}
    client = _client_with(monkeypatch, post)

    result = client.generate(
        model="qwen3:4b",
        prompt="Olá",
        options={"num_ctx": 4096, "temperature": 0.6},
    )

    assert result == "ok"
    assert post.call_args.kwargs["timeout"] == (3.0, 180.0)
    payload = post.call_args.kwargs["json"]
    assert payload == {
        "model": "qwen3:4b",
        "prompt": "Olá",
        "stream": False,
        "options": {"num_ctx": 4096, "temperature": 0.6},
    }


def test_timeout_rejects_nan_and_infinity():
    with pytest.raises(ValueError):
        OllamaClient(timeout=(float("nan"), 180.0))
    with pytest.raises(ValueError):
        OllamaClient(timeout=(3.0, float("inf")))
    with pytest.raises(ValueError):
        OllamaClient(timeout=(0.0, 180.0))


def test_generate_timeout_is_typed_error(monkeypatch):
    post = Mock(side_effect=requests.ReadTimeout("SEGREDO_TESTE"))
    client = _client_with(monkeypatch, post)

    with pytest.raises(OllamaTimeoutError) as caught:
        client.generate(model="qwen3:4b", prompt="Olá")

    assert "SEGREDO_TESTE" not in str(caught.value)
    assert post.call_count == 1


def test_generate_connection_error_is_transport_error(monkeypatch):
    post = Mock(side_effect=requests.ConnectionError("boom"))
    client = _client_with(monkeypatch, post)

    with pytest.raises(OllamaTransportError):
        client.generate(model="qwen3:4b", prompt="Olá")


def test_generate_http_error_is_typed_error(monkeypatch):
    post = Mock()
    post.return_value.raise_for_status.side_effect = requests.HTTPError("SEGREDO_TESTE")
    post.return_value.status_code = 503
    client = _client_with(monkeypatch, post)

    with pytest.raises(OllamaHTTPError) as caught:
        client.generate(model="qwen3:4b", prompt="Olá")

    assert "503" in str(caught.value)
    assert "SEGREDO_TESTE" not in str(caught.value)


def test_generate_invalid_json_is_protocol_error(monkeypatch):
    post = Mock()
    post.return_value.json.side_effect = ValueError("não é JSON")
    client = _client_with(monkeypatch, post)

    with pytest.raises(OllamaProtocolError):
        client.generate(model="qwen3:4b", prompt="Olá")


def test_generate_missing_field_is_protocol_error(monkeypatch):
    post = Mock()
    post.return_value.json.return_value = {}
    client = _client_with(monkeypatch, post)

    with pytest.raises(OllamaProtocolError):
        client.generate(model="qwen3:4b", prompt="Olá")


def test_generate_empty_response_is_valid(monkeypatch):
    post = Mock()
    post.return_value.json.return_value = {"response": ""}
    client = _client_with(monkeypatch, post)

    assert client.generate(model="qwen3:4b", prompt="Olá") == ""


def test_generate_non_stream_returns_str(monkeypatch):
    post = Mock()
    post.return_value.json.return_value = {"response": "texto"}
    client = _client_with(monkeypatch, post)

    result = client.generate(model="qwen3:4b", prompt="Olá", stream=False)

    assert isinstance(result, str)


def test_list_models_empty_list_is_valid(monkeypatch):
    post = Mock()
    post.return_value.json.return_value = {"models": []}
    client = _client_with(monkeypatch, post)

    assert client.list_models() == []


def test_list_models_invalid_entry_is_protocol_error(monkeypatch):
    post = Mock()
    post.return_value.json.return_value = {"models": [{"sem_nome": 1}]}
    client = _client_with(monkeypatch, post)

    with pytest.raises(OllamaProtocolError):
        client.list_models()


def test_list_models_connection_error_is_transport_error(monkeypatch):
    post = Mock(side_effect=requests.ConnectionError("boom"))
    client = _client_with(monkeypatch, post)

    with pytest.raises(OllamaTransportError):
        client.list_models()
