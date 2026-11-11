#!/usr/bin/env python3
"""
Cliente Ollama para inferência local.

Otimizações alinhadas a evidências públicas (docs Ollama + benchmarks 4GB):
- timeout HTTP obrigatório (evita hang infinito)
- keep_alive para evitar reload frio
- num_ctx padrão 2048 (llama3.2:3b cabe 100% na GTX 1650 4GB)
- format=json / schema para saídas estruturadas
- embeddings via /api/embeddings (sem vetores fictícios)
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Sequence
from typing import Any, Literal, overload

import requests
from loguru import logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class OllamaError(RuntimeError):
    """Falha explícita na API Ollama (não mascara como string vazia)."""


DEFAULT_NUM_CTX = int(os.getenv("YBY_OLLAMA_NUM_CTX", "2048"))
DEFAULT_KEEP_ALIVE = os.getenv("YBY_OLLAMA_KEEP_ALIVE", "10m")
DEFAULT_TIMEOUT = float(os.getenv("YBY_OLLAMA_TIMEOUT", "120"))
DEFAULT_CONNECT_TIMEOUT = float(os.getenv("YBY_OLLAMA_CONNECT_TIMEOUT", "5"))
DEFAULT_EMBED_MODEL = os.getenv("YBY_EMBED_MODEL", "all-minilm")


class OllamaClient:
    """Cliente HTTP para API Ollama com sessão reutilizável."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 11434,
        timeout: float = DEFAULT_TIMEOUT,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        keep_alive: str | int = DEFAULT_KEEP_ALIVE,
        num_ctx: int = DEFAULT_NUM_CTX,
        embed_model: str = DEFAULT_EMBED_MODEL,
    ):
        self.base_url = f"http://{host}:{port}"
        self.timeout = (connect_timeout, timeout)
        self.keep_alive = keep_alive
        self.num_ctx = num_ctx
        self.embed_model = embed_model

        self.session = requests.Session()
        retries = Retry(
            total=2,
            backoff_factor=0.3,
            status_forcelist=(502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=4, pool_maxsize=4)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        logger.info(
            f"🦙 OllamaClient em {self.base_url} "
            f"(num_ctx={num_ctx}, keep_alive={keep_alive}, timeout={timeout}s)"
        )

    def _merge_options(self, options: dict[str, Any] | None) -> dict[str, Any]:
        merged = {"num_ctx": self.num_ctx}
        if options:
            merged.update(options)
        return merged

    def pull(self, model: str) -> bool:
        """Baixa modelo Ollama com timeout e verificação de status."""
        try:
            logger.info(f"📥 Baixando modelo: {model}")
            response = self.session.post(
                f"{self.base_url}/api/pull",
                json={"name": model},
                stream=True,
                timeout=self.timeout,
            )
            response.raise_for_status()

            success = False
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug(f"  {line}")
                    continue
                status = payload.get("status", "")
                logger.debug(f"  {status}")
                if status == "success" or payload.get("completed"):
                    success = True

            if not success:
                logger.error(f"❌ Pull incompleto: {model}")
                return False

            logger.info(f"✅ Modelo {model} baixado")
            return True

        except requests.RequestException as exc:
            logger.error(f"❌ Erro ao baixar {model}: {exc}")
            return False

    @overload
    def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        stream: Literal[False] = False,
        options: dict[str, Any] | None = None,
        keep_alive: str | int | None = None,
        format: str | dict[str, Any] | None = None,
    ) -> str: ...

    @overload
    def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        stream: Literal[True] = True,
        options: dict[str, Any] | None = None,
        keep_alive: str | int | None = None,
        format: str | dict[str, Any] | None = None,
    ) -> Iterator[str]: ...

    def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        stream: bool = False,
        options: dict[str, Any] | None = None,
        keep_alive: str | int | None = None,
        format: str | dict[str, Any] | None = None,
    ) -> str | Iterator[str]:
        """Gera resposta com modelo Ollama."""
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "keep_alive": keep_alive if keep_alive is not None else self.keep_alive,
            "options": self._merge_options(options),
        }
        if system:
            payload["system"] = system
        if format is not None:
            payload["format"] = format

        try:
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=stream,
                timeout=self.timeout,
            )
            response.raise_for_status()

            if stream:

                def stream_generator() -> Iterator[str]:
                    for line in response.iter_lines(decode_unicode=True):
                        if line:
                            yield line

                return stream_generator()

            result = response.json()
            text = result.get("response", "")
            if not text:
                raise OllamaError(f"Resposta vazia do modelo {model}")
            return text

        except requests.RequestException as exc:
            logger.error(f"❌ Erro ao gerar com {model}: {exc}")
            raise OllamaError(f"Falha HTTP Ollama: {exc}") from exc

    @overload
    def chat(
        self,
        model: str,
        messages: list,
        stream: Literal[False] = False,
        options: dict[str, Any] | None = None,
        keep_alive: str | int | None = None,
        format: str | dict[str, Any] | None = None,
    ) -> str: ...

    @overload
    def chat(
        self,
        model: str,
        messages: list,
        stream: Literal[True] = True,
        options: dict[str, Any] | None = None,
        keep_alive: str | int | None = None,
        format: str | dict[str, Any] | None = None,
    ) -> Iterator[str]: ...

    def chat(
        self,
        model: str,
        messages: list,
        stream: bool = False,
        options: dict[str, Any] | None = None,
        keep_alive: str | int | None = None,
        format: str | dict[str, Any] | None = None,
    ) -> str | Iterator[str]:
        """Chat com histórico de mensagens."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "keep_alive": keep_alive if keep_alive is not None else self.keep_alive,
            "options": self._merge_options(options),
        }
        if format is not None:
            payload["format"] = format

        try:
            response = self.session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=stream,
                timeout=self.timeout,
            )
            response.raise_for_status()

            if stream:

                def stream_generator() -> Iterator[str]:
                    for line in response.iter_lines(decode_unicode=True):
                        if line:
                            yield line

                return stream_generator()

            result = response.json()
            text = result.get("message", {}).get("content", "")
            if not text:
                raise OllamaError(f"Chat vazio do modelo {model}")
            return text

        except requests.RequestException as exc:
            logger.error(f"❌ Erro no chat com {model}: {exc}")
            raise OllamaError(f"Falha HTTP Ollama chat: {exc}") from exc

    def embed(
        self,
        texts: str | Sequence[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Gera embeddings reais via /api/embeddings (nunca vetores fictícios)."""
        embed_model = model or self.embed_model
        inputs = [texts] if isinstance(texts, str) else list(texts)
        if not inputs:
            raise OllamaError("embed() requer ao menos um texto")

        vectors: list[list[float]] = []
        for text in inputs:
            try:
                response = self.session.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": embed_model, "prompt": text},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
                embedding = payload.get("embedding")
                if not isinstance(embedding, list) or not embedding:
                    raise OllamaError(
                        f"Embedding vazio do modelo {embed_model}. "
                        f"Verifique se o modelo está instalado (ollama pull {embed_model})."
                    )
                if all(v == 0 for v in embedding):
                    raise OllamaError(
                        f"Embedding zerado rejeitado ({embed_model}) — possível stub."
                    )
                vectors.append([float(v) for v in embedding])
            except requests.RequestException as exc:
                logger.error(f"❌ Erro ao embedder com {embed_model}: {exc}")
                raise OllamaError(f"Falha HTTP Ollama embeddings: {exc}") from exc

        return vectors

    def list_models(self) -> list[str]:
        """Lista modelos disponíveis."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            return [m["name"] for m in result.get("models", [])]
        except requests.RequestException as exc:
            logger.error(f"❌ Erro ao listar modelos: {exc}")
            return []

    def is_healthy(self) -> bool:
        """Verifica se Ollama está rodando."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=(self.timeout[0], min(5.0, self.timeout[1])),
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def close(self) -> None:
        self.session.close()
