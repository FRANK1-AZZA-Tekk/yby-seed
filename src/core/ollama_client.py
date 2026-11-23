#!/usr/bin/env python3
"""
Cliente Ollama para inferência local de modelos (legado; agentes em src/agents).

Uso:
    ollama = OllamaClient(host="localhost", port=11434)
    response = ollama.generate("qwen2.5-coder:3b", "Olá!")
"""

from __future__ import annotations

from typing import Any, Iterator, Optional

import requests
from loguru import logger


class OllamaClientError(RuntimeError):
    """Falha de rede ou HTTP ao falar com o Ollama."""


class OllamaClient:
    """Cliente HTTP para API Ollama."""

    def __init__(self, host: str = "localhost", port: int = 11434) -> None:
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
        logger.info(f"OllamaClient conectado em {self.base_url}")

    def close(self) -> None:
        self.session.close()

    def pull(self, model: str) -> bool:
        """Baixa modelo Ollama."""
        try:
            logger.info(f"Baixando modelo: {model}")
            response = self.session.post(
                f"{self.base_url}/api/pull",
                json={"name": model},
                stream=True,
                timeout=(5.0, 300.0),
            )
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    logger.debug(f"  {line.decode()}")
            logger.info(f"Modelo {model} baixado")
            return True
        except requests.RequestException as exc:
            logger.error(f"Erro ao baixar {model}: {exc}")
            return False

    def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        stream: bool = False,
        options: Optional[dict[str, Any]] = None,
    ) -> str | Iterator[str]:
        """Gera resposta com modelo Ollama."""

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options

        try:
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=stream,
                timeout=(5.0, 120.0),
            )
            response.raise_for_status()
        except (requests.RequestException, OSError) as exc:
            logger.error(f"Erro ao gerar com {model}: {exc}")
            raise OllamaClientError(f"generate falhou para {model}") from exc

        if stream:

            def stream_generator() -> Iterator[str]:
                for line in response.iter_lines():
                    if line:
                        yield line.decode()

            return stream_generator()

        result = response.json()
        if not isinstance(result, dict):
            raise OllamaClientError("generate devolveu JSON inválido")
        error = result.get("error")
        if isinstance(error, str) and error.strip():
            raise OllamaClientError(f"Ollama: {error.strip()}")
        return str(result.get("response", ""))

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool = False,
    ) -> str | Iterator[str]:
        """Chat com histórico de mensagens."""

        payload = {"model": model, "messages": messages, "stream": stream}
        try:
            response = self.session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=stream,
                timeout=(5.0, 120.0),
            )
            response.raise_for_status()
        except (requests.RequestException, OSError) as exc:
            logger.error(f"Erro no chat com {model}: {exc}")
            raise OllamaClientError(f"chat falhou para {model}") from exc

        if stream:

            def stream_generator() -> Iterator[str]:
                for line in response.iter_lines():
                    if line:
                        yield line.decode()

            return stream_generator()

        result = response.json()
        if not isinstance(result, dict):
            raise OllamaClientError("chat devolveu JSON inválido")
        message = result.get("message")
        if not isinstance(message, dict):
            raise OllamaClientError("chat sem campo message")
        return str(message.get("content", ""))

    def list_models(self) -> list[str]:
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                return []
            models = result.get("models", [])
            if not isinstance(models, list):
                return []
            return [str(m["name"]) for m in models if isinstance(m, dict) and "name" in m]
        except requests.RequestException as exc:
            logger.error(f"Erro ao listar modelos: {exc}")
            return []

    def is_healthy(self) -> bool:
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False