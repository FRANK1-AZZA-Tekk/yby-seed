#!/usr/bin/env python3
"""
Cliente Ollama para inferência local de modelos.

Uso:
    ollama = OllamaClient(host="localhost", port=11434)
    response = ollama.generate("llama3.2:3b", "Olá!")
"""

import requests
from typing import Optional, Dict, Any
from loguru import logger


class OllamaError(Exception):
    """Erro base para falhas na comunicação com o Ollama."""


class OllamaTimeoutError(OllamaError):
    """Ollama não respondeu dentro do tempo limite."""


class OllamaConnectionError(OllamaError):
    """Não foi possível conectar ao Ollama."""


class OllamaHTTPError(OllamaError):
    """Ollama retornou um erro HTTP."""


class OllamaClient:
    """Cliente HTTP para a API do Ollama com timeout e erros tipados."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 11434,
        timeout: int = 120,
    ):
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        self.session = requests.Session()
        logger.info(f"🦙 OllamaClient conectado em {self.base_url}")

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Executa requisição com timeout e tradução de erros."""
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                timeout=self.timeout,
                **kwargs,
            )
            response.raise_for_status()
            return response
        except requests.Timeout as e:
            logger.error(f"⏱️ Timeout ao chamar Ollama ({path}): {e}")
            raise OllamaTimeoutError(
                f"Ollama não respondeu em {self.timeout}s ({path})"
            ) from e
        except requests.ConnectionError as e:
            logger.error(f"🔌 Falha de conexão com Ollama ({path}): {e}")
            raise OllamaConnectionError(
                f"Não foi possível conectar ao Ollama em {self.base_url}"
            ) from e
        except requests.HTTPError as e:
            logger.error(f"❌ Erro HTTP do Ollama ({path}): {e}")
            raise OllamaHTTPError(
                f"Ollama retornou erro HTTP: {e.response.status_code}"
            ) from e

    def pull(self, model: str) -> bool:
        """Baixa modelo Ollama."""
        try:
            logger.info(f"📥 Baixando modelo: {model}")
            response = self._request(
                "POST", "/api/pull", json={"name": model}, stream=True
            )

            for line in response.iter_lines():
                if line:
                    logger.debug(f"  {line.decode()}")

            logger.info(f"✅ Modelo {model} baixado")
            return True
        except OllamaError as e:
            logger.error(f"❌ Erro ao baixar {model}: {e}")
            return False

    def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        stream: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Gera resposta com modelo Ollama."""
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }

        if system:
            payload["system"] = system

        if options:
            payload["options"] = options

        response = self._request(
            "POST", "/api/generate", json=payload, stream=stream
        )

        if stream:
            def stream_generator():
                for line in response.iter_lines():
                    if line:
                        yield line.decode()

            return stream_generator()

        result = response.json()
        return result.get("response", "")

    def chat(
        self,
        model: str,
        messages: list,
        stream: bool = False,
    ) -> str:
        """Chat com histórico de mensagens."""
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        response = self._request(
            "POST", "/api/chat", json=payload, stream=stream
        )

        if stream:
            def stream_generator():
                for line in response.iter_lines():
                    if line:
                        yield line.decode()

            return stream_generator()

        result = response.json()
        return result.get("message", {}).get("content", "")

    def list_models(self) -> list:
        """Lista modelos disponíveis."""
        try:
            response = self._request("GET", "/api/tags")
            result = response.json()
            return [m["name"] for m in result.get("models", [])]
        except OllamaError as e:
            logger.error(f"❌ Erro ao listar modelos: {e}")
            return []

    def is_healthy(self) -> bool:
        """Verifica se Ollama está rodando."""
        try:
            response = self._request("GET", "/api/tags")
            return response.status_code == 200
        except OllamaError:
            return False
