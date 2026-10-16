#!/usr/bin/env python3
"""
Cliente Ollama para inferência local de modelos.

Política de transporte: apenas endpoints loopback (localhost/127.0.0.1
ou ::1), sem proxies por ambiente e sem redirecionamentos.

Erros de timeout, transporte, HTTP, protocolo e política são reportados
como exceções tipadas. Mensagens públicas nunca incluem prompt, resposta,
corpo HTTP ou mensagem original da exceção.
"""

import math
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


class OllamaPolicyError(OllamaClientError):
    """Operação bloqueada pela política de transporte."""


def _loopback_base_url(host: str, port: int) -> str:
    if type(port) is not int or not 1 <= port <= 65535:
        raise OllamaPolicyError(
            "Porta do Ollama não permitida pela política local."
        )

    if host in ("localhost", "127.0.0.1"):
        return f"http://127.0.0.1:{port}"

    if host == "::1":
        return f"http://[::1]:{port}"

    raise OllamaPolicyError(
        "Endpoint do Ollama não permitido pela política local."
    )


class OllamaClient:
    """Cliente HTTP para API Ollama."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 11434,
        *,
        timeout: tuple[float, float] = (3.0, 180.0),
    ):
        if (
            len(timeout) != 2
            or any(not math.isfinite(t) or t <= 0 for t in timeout)
        ):
            raise ValueError(
                "timeout deve ser (conexao, leitura) com valores positivos e finitos"
            )
        self.base_url = _loopback_base_url(host, port)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = False
        logger.info("OllamaClient configurado para endpoint loopback.")

    def _request(
        self,
        method: str,
        path: str,
        *,
        stream: bool = False,
        json_payload: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> requests.Response:
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                json=json_payload,
                stream=stream,
                timeout=self.timeout if timeout is None else timeout,
                allow_redirects=False,
            )
        except requests.Timeout:
            raise OllamaTimeoutError(
                "Tempo de espera excedido ao consultar o Ollama."
            ) from None
        except requests.RequestException:
            raise OllamaTransportError(
                "Falha de conexão com o Ollama."
            ) from None

        if 300 <= response.status_code < 400:
            response.close()
            raise OllamaPolicyError(
                "Redirecionamento bloqueado pela política local."
            )

        return response

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
        """Baixa modelo Ollama (resultado legado; endurecimento completo no 2B)."""
        try:
            logger.info("Baixando modelo: {}", model)
            response = self._request(
                "POST",
                "/api/pull",
                json_payload={"name": model},
                stream=True,
            )
            for line in response.iter_lines():
                if line:
                    logger.debug("pull: {}", line.decode())
            logger.info("Modelo {} baixado", model)
            return True
        except OllamaPolicyError:
            raise
        except Exception:
            logger.error("Erro ao baixar {}", model)
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
        """Chat com histórico (resultado legado; endurecimento completo no 2B)."""
        payload = {"model": model, "messages": messages, "stream": stream}
        try:
            response = self._request(
                "POST", "/api/chat", json_payload=payload, stream=stream
            )
            if stream:
                def stream_generator():
                    for line in response.iter_lines():
                        if line:
                            yield line.decode()
                return stream_generator()
            result = response.json()
            return result.get("message", {}).get("content", "")
        except OllamaPolicyError:
            raise
        except Exception:
            logger.error("Erro no chat com {}", model)
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
        """Sonda disponibilidade sem ocultar bloqueios de política."""
        try:
            response = self._request(
                "GET",
                "/api/tags",
                timeout=5.0,
            )
            try:
                return response.status_code == 200
            finally:
                response.close()
        except OllamaPolicyError:
            raise
        except OllamaClientError:
            return False
