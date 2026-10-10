import json

import pytest
import requests

from src.core.ollama_client import (
    OllamaClient,
    OllamaHTTPError,
    OllamaProtocolError,
)


class FakeResponse:
    def __init__(self, payload=None, status=200, lines=None, json_error=None):
        self.payload = payload
        self.status_code = status
        self.lines = lines or []
        self.json_error = json_error
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload

    def iter_lines(self, decode_unicode=False):
        yield from self.lines

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, post_response=None, get_response=None, post_error=None):
        self.post_response = post_response
        self.get_response = get_response
        self.post_error = post_error
        self.kwargs = None

    def post(self, url, **kwargs):
        self.kwargs = kwargs
        if self.post_error:
            raise self.post_error
        return self.post_response

    def get(self, url, **kwargs):
        self.kwargs = kwargs
        return self.get_response


def test_generate_success_and_timeout_passed():
    response = FakeResponse({"response": "olá"})
    session = FakeSession(post_response=response)
    client = OllamaClient(session=session, timeout=(2, 10))
    assert client.generate("model", "oi") == "olá"
    assert session.kwargs["timeout"] == (2, 10)
    assert response.closed


def test_http_error_is_not_hidden():
    session = FakeSession(post_error=requests.Timeout("timeout"))
    client = OllamaClient(session=session)
    with pytest.raises(OllamaHTTPError):
        client.generate("model", "oi")


def test_invalid_json_response_raises_protocol_error():
    response = FakeResponse(json_error=json.JSONDecodeError("bad", "x", 0))
    client = OllamaClient(session=FakeSession(post_response=response))
    with pytest.raises(OllamaProtocolError):
        client.generate("model", "oi")
    assert response.closed


def test_stream_closes_response_after_consumption():
    response = FakeResponse(lines=[b'{"response":"a"}', b'{"response":"b"}'])
    client = OllamaClient(session=FakeSession(post_response=response))
    assert list(client.generate("model", "oi", stream=True)) == ['{"response":"a"}', '{"response":"b"}']
    assert response.closed


def test_list_models_http_error_raises():
    response = FakeResponse(status=503)
    client = OllamaClient(session=FakeSession(get_response=response))
    with pytest.raises(OllamaHTTPError):
        client.list_models()
