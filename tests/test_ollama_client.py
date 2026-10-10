import json

import pytest
import requests

from src.core.ollama_client import OllamaClient, OllamaClientError, OllamaHTTPError, OllamaProtocolError


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
    def __init__(self, post_response=None, get_response=None, post_error=None, get_error=None):
        self.post_response = post_response
        self.get_response = get_response
        self.post_error = post_error
        self.get_error = get_error
        self.kwargs = None

    def post(self, url, **kwargs):
        self.kwargs = kwargs
        if self.post_error:
            raise self.post_error
        return self.post_response

    def get(self, url, **kwargs):
        self.kwargs = kwargs
        if self.get_error:
            raise self.get_error
        return self.get_response


def test_generate_success_closes_response_and_sets_timeout():
    response = FakeResponse({"response": "olá"})
    session = FakeSession(post_response=response)
    client = OllamaClient(session=session, timeout=(2.0, 10.0))
    assert client.generate("model", "oi") == "olá"
    assert session.kwargs["timeout"] == (2.0, 10.0)
    assert response.closed


def test_timeout_is_reported_as_http_error():
    session = FakeSession(post_error=requests.Timeout("timeout"))
    with pytest.raises(OllamaHTTPError):
        OllamaClient(session=session).generate("model", "oi")


def test_http_status_error_closes_response():
    response = FakeResponse(status=503)
    with pytest.raises(OllamaHTTPError):
        OllamaClient(session=FakeSession(post_response=response)).generate("model", "oi")
    assert response.closed


def test_invalid_json_raises_protocol_error_and_closes():
    response = FakeResponse(json_error=json.JSONDecodeError("bad", "x", 0))
    with pytest.raises(OllamaProtocolError):
        OllamaClient(session=FakeSession(post_response=response)).generate("model", "oi")
    assert response.closed


def test_stream_parses_events_and_closes():
    response = FakeResponse(lines=[b'{"response":"a"}', b'{"response":"b"}'])
    chunks = OllamaClient(session=FakeSession(post_response=response)).generate("model", "oi", stream=True)
    assert list(chunks) == ['{"response":"a"}', '{"response":"b"}']
    assert response.closed


def test_stream_closes_if_consumer_stops_early():
    response = FakeResponse(lines=[b'{"response":"a"}', b'{"response":"b"}'])
    chunks = OllamaClient(session=FakeSession(post_response=response)).generate("model", "oi", stream=True)
    next(chunks)
    chunks.close()
    assert response.closed


def test_stream_propagates_ollama_error_and_closes():
    response = FakeResponse(lines=[b'{"error":"model not found"}'])
    chunks = OllamaClient(session=FakeSession(post_response=response)).generate("model", "oi", stream=True)
    with pytest.raises(OllamaClientError):
        list(chunks)
    assert response.closed


def test_list_models_rejects_invalid_shape_and_closes():
    response = FakeResponse({"models": ["not-an-object"]})
    with pytest.raises(OllamaProtocolError):
        OllamaClient(session=FakeSession(get_response=response)).list_models()
    assert response.closed
