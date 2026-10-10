#!/usr/bin/env python3
"""Cliente HTTP defensivo para a API local do Ollama."""

from __future__ import annotations

import json
from typing import Any, Iterator
from urllib.parse import urlsplit

import requests
from loguru import logger


class OllamaClientError(RuntimeError):
    """Erro base do cliente Ollama."""


class OllamaHTTPError(OllamaClientError):
    """O servidor Ollama respondeu com status HTTP não exitoso."""


class OllamaProtocolError(OllamaClientError):
    """Resposta Ollama inválida ou incompleta."""


class OllamaClient:
    """Cliente síncrono para endpoints nativos do Ollama."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 11434,
        timeout: float | tuple[float, float] = (5.0, 120.0),
        session: requests.Session | None = None,
    ) -> None:
        if not 1 <= port <= 65535:
            raise ValueError("port deve estar entre 1 e 65535")
        if isinstance(timeout, (int, float)) and timeout <= 0:
            raise ValueError("timeout deve ser positivo")
        if isinstance(timeout, tuple) and (len(timeout) != 2 or any(v <= 0 for v in timeout)):
            raise ValueError("timeout tuple deve conter connect/read positivos")
        if not host or any(c in host for c in "/?#@"):
            raise ValueError("host inválido; passe hostname/IP, não URL")

        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        self.session = session or requests.Session()
        logger.info("OllamaClient configurado para {}", self.base_url)

    def _post_json(self, endpoint: str, payload: dict[str, Any], stream: bool = False) -> requests.Response:
        try:
            response = self.session.post(
                f"{self.base_url}{endpoint}",
                json=payload,
                stream=stream,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            raise OllamaHTTPError(f"Falha HTTP na chamada Ollama {endpoint}: {exc}") from exc

    @staticmethod
    def _json(response: requests.Response) -> dict[str, Any]:
        try:
            value = response.json()
        except (requests.exceptions.JSONDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise OllamaProtocolError("Ollama retornou JSON inválido") from exc
        if not isinstance(value, dict):
            raise OllamaProtocolError("Ollama retornou JSON com formato inesperado")
        return value

    @staticmethod
    def _stream_lines(response: requests.Response) -> Iterator[str]:
        try:
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    yield line if isinstance(line, str) else line.decode("utf-8")
        finally:
            response.close()

    def pull(self, model: str) -> bool:
        if not model.strip():
            raise ValueError("model não pode ser vazio")
        response = self._post_json("/api/pull", {"name": model, "stream": True}, stream=True)
        try:
            for line in self._stream_lines(response):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise OllamaProtocolError("Evento de pull contém JSON inválido") from exc
                if event.get("error"):
                    raise OllamaClientError(f"Ollama pull falhou: {event['error']}")
            return True
        finally:
            response.close()

    def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        stream: bool = False,
        options: dict[str, Any] | None = None,
    ) -> str | Iterator[str]:
        if not model.strip() or not prompt.strip():
            raise ValueError("model e prompt não podem ser vazios")
        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": stream}
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options
        response = self._post_json("/api/generate", payload, stream=stream)
        if stream:
            return self._stream_lines(response)
        try:
            result = self._json(response)
            text = result.get("response")
            if not isinstance(text, str):
                raise OllamaProtocolError("Resposta Ollama sem campo 'response' textual")
            return text
        finally:
            response.close()

    def chat(self, model: str, messages: list[dict[str, Any]], stream: bool = False) -> str | Iterator[str]:
        if not model.strip() or not messages:
            raise ValueError("model e messages não podem estar vazios")
        response = self._post_json(
            "/api/chat",
            {"model": model, "messages": messages, "stream": stream},
            stream=stream,
        )
        if stream:
            return self._stream_lines(response)
        try:
            result = self._json(response)
            message = result.get("message")
            text = message.get("content") if isinstance(message, dict) else None
            if not isinstance(text, str):
                raise OllamaProtocolError("Resposta Ollama sem message.content textual")
            return text
        finally:
            response.close()

    def list_models(self) -> list[str]:
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OllamaHTTPError(f"Falha ao listar modelos Ollama: {exc}") from exc
        try:
            result = self._json(response)
            models = result.get("models", [])
            if not isinstance(models, list) or any(not isinstance(m, dict) or not isinstance(m.get("name"), str) for m in models):
                raise OllamaProtocolError("Lista de modelos Ollama inválida")
            return [m["name"] for m in models]
        finally:
            response.close()

    def is_healthy(self) -> bool:
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            return response.status_code == 200
        except requests.RequestException:
            return False
