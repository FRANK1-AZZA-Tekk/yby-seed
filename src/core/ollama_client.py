#!/usr/bin/env python3
"""
Cliente Ollama para inferência local de modelos.

Erros de timeout, transporte, HTTP e protocolo são reportados como
exceções tipadas. Mensagens públicas nunca incluem prompt, resposta,
corpo HTTP ou mensagem original da exceção.
"""

from typing import Any, Dict, Iterator, Optional, Union

import requests
from loguru import logger


class OllamaClientError(RuntimeError):
    """Falha segura para apresentação pelo CLI."""


class OllamaTimeoutError(OllamaClientError):
    """Tempo de espera excedido ao consultar o Ollama."""


class OllamaTransportError(OllamaClientError):
    """Falha de conexão com o Ollama."""


class OllamaHTTPError(OllamaClientError):
    """Ollama retornou status HTTP de erro."""


class OllamaProtocolError(OllamaClientError):
    """Resposta inválida recebida do Ollama."""


class OllamaClient:
    """Cliente HTTP para API Ollama."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 11434,
        *,
        timeout: tuple[float, float] = (3.0, 180.0),
    ):
        if len(timeout) != 2 or timeout[0] <= 0 or timeout[1] <= 0:
            raise ValueError("timeout deve ser (conexao, leitura) com valores positivos")
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        self.session = requests.Session()
        logger.info("OllamaClient conectado em %s", self.base_url)

    def _request(
        self,
        method: str,
        path: str,
        *,
        stream: bool = False,
        json_payload: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        try:
            return self.session.request(
                method,
                f"{self.base_url}{path}",
                json=json_payload,
                stream=stream,
                timeout=self.timeout,
            )
        except requests.Timeout:
            raise OllamaTimeoutError(
                "Tempo de espera excedido ao consultar o Ollama."
            ) from None
        except requests.RequestException:
            raise OllamaTransportError("Falha de conexão com o Ollama.") from None

    def _json_object(self, response: requests.Response) -> Dict[str, Any]:
        try:
            response.raise_for_status()
        except requests.HTTPError:
            status = response.status_code
            response.close()
            raise OllamaHTTPError(f"Ollama retornou erro HTTP {status}.") from None
        try:
            data = response.json()
        except ValueError:
            response.close()
            raise OllamaProtocolError(
                "Resposta inválida recebida do Ollama."
            ) from None
        response.close()
        if not isinstance(data, dict):
            raise OllamaProtocolError("Resposta inválida recebida do Ollama.")
        if "error" in data:
            raise OllamaProtocolError("Ollama reportou erro na operação.")
        return data

    def pull(self, model: str) -> bool:
        """Baixa modelo Ollama (contrato anterior preservado; 2B depois)."""
        try:
            logger.info("Baixando modelo: %s", model)
            response = self.session.post(
                f"{self.base_url}/api/pull", json={"name": model}, stream=True
            )
            for line in response.iter_lines():
                if line:
                    logger.debug("pull: %s", line.decode())
            logger.info("Modelo %s baixado", model)
            return True
        except Exception:
            logger.error("Erro ao baixar %s", model)
            return False

    def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        stream: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Union[str, Iterator[str]]:
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

        if stream:
            response = self._request(
                "POST", "/api/generate", stream=True, json_payload=payload
            )
            try:
                response.raise_for_status()
            except requests.HTTPError:
                status = response.status_code
                response.close()
                raise OllamaHTTPError(
                    f"Ollama retornou erro HTTP {status}."
                ) from None

            def stream_generator() -> Iterator[str]:
                try:
                    for line in response.iter_lines():
                        if line:
                            yield line.decode()
                finally:
                    response.close()

            return stream_generator()

        data = self._json_object(
            self._request("POST", "/api/generate", json_payload=payload)
        )
        if "response" not in data or not isinstance(data["response"], str):
            raise OllamaProtocolError("Resposta inválida recebida do Ollama.")
        return data["response"]

    def chat(
        self,
        model: str,
        messages: list,
        stream: bool = False,
    ) -> str:
        """Chat com histórico (contrato anterior preservado; endurecimento no 2B)."""
        payload = {"model": model, "messages": messages, "stream": stream}
        try:
            response = self.session.post(
                f"{self.base_url}/api/chat", json=payload, stream=stream
            )
            if stream:
                def stream_generator():
                    for line in response.iter_lines():
                        if line:
                            yield line.decode()
                return stream_generator()
            result = response.json()
            return result.get("message", {}).get("content", "")
        except Exception:
            logger.error("Erro no chat com %s", model)
            return ""

    def list_models(self) -> list:
        """Lista modelos disponíveis."""
        data = self._json_object(self._request("GET", "/api/tags"))
        models = data.get("models")
        if not isinstance(models, list):
            raise OllamaProtocolError("Resposta inválida recebida do Ollama.")
        names = []
        for item in models:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise OllamaProtocolError("Resposta inválida recebida do Ollama.")
            names.append(item["name"])
        return names

    def is_healthy(self) -> bool:
        """Verifica se Ollama está rodando."""
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
