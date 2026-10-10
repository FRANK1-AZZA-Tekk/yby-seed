#!/usr/bin/env python3
"""Cliente HTTP defensivo para a API local do Ollama."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import requests
from loguru import logger


class OllamaClientError(RuntimeError):
    """Erro base do cliente Ollama."""


class OllamaHTTPError(OllamaClientError):
    """Falha de transporte, timeout ou status HTTP não exitoso."""


class OllamaProtocolError(OllamaClientError):
    """Resposta JSON ou evento de streaming inválido."""


class OllamaClient:
    """Cliente síncrono para endpoints nativos do Ollama."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 11434,
        timeout: float | tuple[float, float] = (5.0, 120.0),
        session: requests.Session | None = None,
    ) -> None:
        if not host or any(char in host for char in "/?#@"):
            raise ValueError("host deve ser hostname/IP, não uma URL")
        if not 1 <= port <= 65535:
            raise ValueError("port deve estar entre 1 e 65535")
        if isinstance(timeout, (int, float)):
            valid_timeout = timeout > 0
        else:
            valid_timeout = len(timeout) == 2 and all(value > 0 for value in timeout)
        if not valid_timeout:
            raise ValueError("timeout deve ser positivo ou tupla (connect, read) positiva")

        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        self.session = session or requests.Session()
        logger.info("OllamaClient configurado para {}", self.base_url)

    def _post(self, endpoint: str, payload: dict[str, Any], stream: bool = False) -> requests.Response:
        try:
            response = self.session.post(
                f"{self.base_url}{endpoint}", json=payload, stream=stream, timeout=self.timeout
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            if "response" in locals():
                response.close()
            raise OllamaHTTPError(f"Falha na chamada Ollama {endpoint}: {exc}") from exc

    def _get(self, endpoint: str) -> requests.Response:
        try:
            response = self.session.get(f"{self.base_url}{endpoint}", timeout=self.timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            if "response" in locals():
                response.close()
            raise OllamaHTTPError(f"Falha na chamada Ollama {endpoint}: {exc}") from exc

    @staticmethod
    def _parse_json(response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError) as exc:
            raise OllamaProtocolError("Ollama retornou JSON inválido") from exc
        if not isinstance(data, dict):
            raise OllamaProtocolError("Ollama retornou JSON com formato inesperado")
        return data

    @staticmethod
    def _iter_stream(response: requests.Response) -> Iterator[str]:
        try:
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                text = line if isinstance(line, str) else line.decode("utf-8")
                try:
                    event = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise OllamaProtocolError("Ollama retornou evento de streaming inválido") from exc
                if not isinstance(event, dict):
                    raise OllamaProtocolError("Evento de streaming Ollama deve ser um objeto JSON")
                if event.get("error"):
                    raise OllamaClientError(f"Ollama retornou erro: {event['error']}")
                yield text
        finally:
            response.close()

    def pull(self, model: str) -> bool:
        if not model.strip():
            raise ValueError("model não pode ser vazio")
        response = self._post("/api/pull", {"name": model, "stream": True}, stream=True)
        for _ in self._iter_stream(response):
            pass
        return True

    def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        stream: bool = False,
        options: dict[str, Any] | None = None,
    ) -> str | Iterator[str]:
        if not model.strip() or not prompt.strip():
            raise ValueError("model e prompt não podem estar vazios")
        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": stream}
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options
        response = self._post("/api/generate", payload, stream=stream)
        if stream:
            return self._iter_stream(response)
        try:
            result = self._parse_json(response)
            text = result.get("response")
            if not isinstance(text, str):
                raise OllamaProtocolError("Resposta Ollama sem campo response textual")
            return text
        finally:
            response.close()

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool = False,
    ) -> str | Iterator[str]:
        if not model.strip() or not messages:
            raise ValueError("model e messages não podem estar vazios")
        response = self._post(
            "/api/chat", {"model": model, "messages": messages, "stream": stream}, stream=stream
        )
        if stream:
            return self._iter_stream(response)
        try:
            result = self._parse_json(response)
            message = result.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, str):
                raise OllamaProtocolError("Resposta Ollama sem message.content textual")
            return content
        finally:
            response.close()

    def list_models(self) -> list[str]:
        response = self._get("/api/tags")
        try:
            result = self._parse_json(response)
            models = result.get("models")
            if not isinstance(models, list):
                raise OllamaProtocolError("Resposta Ollama sem lista models")
            names = [item.get("name") for item in models if isinstance(item, dict)]
            if len(names) != len(models) or any(not isinstance(name, str) for name in names):
                raise OllamaProtocolError("Lista de modelos Ollama contém item inválido")
            return names
        finally:
            response.close()

    def is_healthy(self) -> bool:
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            try:
                return response.status_code == 200
            finally:
                response.close()
        except requests.RequestException:
            return False
