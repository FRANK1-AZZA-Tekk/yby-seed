"""Testes do OllamaClient otimizado (sem servidor real)."""

from unittest.mock import MagicMock, patch

import pytest
import requests
from src.core.ollama_client import DEFAULT_NUM_CTX, OllamaClient, OllamaError


def test_defaults_4gb_friendly():
    client = OllamaClient()
    assert client.num_ctx == DEFAULT_NUM_CTX
    assert DEFAULT_NUM_CTX == 2048
    assert client.keep_alive == "10m"
    client.close()


def test_generate_raises_on_http_error():
    client = OllamaClient()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("boom")
    with (
        patch.object(client.session, "post", return_value=mock_resp),
        pytest.raises(OllamaError),
    ):
        client.generate("llama3.2:3b", "oi")
    client.close()


def test_generate_merges_num_ctx():
    client = OllamaClient(num_ctx=2048)
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"response": "ok"}
    with patch.object(client.session, "post", return_value=mock_resp) as post:
        text = client.generate("llama3.2:3b", "oi", options={"temperature": 0.1})
        assert text == "ok"
        payload = post.call_args.kwargs["json"]
        assert payload["options"]["num_ctx"] == 2048
        assert payload["options"]["temperature"] == 0.1
        assert payload["keep_alive"] == "10m"
        assert "timeout" in post.call_args.kwargs
    client.close()


def test_generate_passes_format_json():
    client = OllamaClient()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"response": '{"a":1}'}
    with patch.object(client.session, "post", return_value=mock_resp) as post:
        client.generate("llama3.2:3b", "oi", format="json")
        assert post.call_args.kwargs["json"]["format"] == "json"
    client.close()


def test_embed_rejects_empty_and_zero_vector():
    client = OllamaClient()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"embedding": [0.0, 0.0]}
    with (
        patch.object(client.session, "post", return_value=mock_resp),
        pytest.raises(OllamaError, match="zerado|vazio|Embedding"),
    ):
        client.embed("texto")
    client.close()


def test_embed_ok():
    client = OllamaClient()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
    with patch.object(client.session, "post", return_value=mock_resp) as post:
        vectors = client.embed("texto")
        assert vectors == [[0.1, 0.2, 0.3]]
        assert post.call_args.kwargs["json"]["model"] == client.embed_model
    client.close()
