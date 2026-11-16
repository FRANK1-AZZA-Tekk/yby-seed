"""Ollama tuning e política de nuvem (D12) nos provedores."""

from __future__ import annotations

import pytest
import requests

from src.engine.providers import (
    CascadingCloudProvider,
    CloudProvider,
    OllamaProvider,
    ProviderError,
    ProviderUnreachable,
    build_ollama_generate_payload,
)


class _Resp:
    def __init__(self, status: int, payload: object | None = None) -> None:
        self.status_code = status
        self._payload = payload or {"response": "ok"}

    def json(self) -> object:
        return self._payload


class _Session:
    def __init__(
        self,
        response: _Resp | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response or _Resp(200)
        self.error = error
        self.posts: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> _Resp:
        self.posts.append({"url": url, **kwargs})
        if self.error:
            raise self.error
        return self.response


def test_ollama_payload_defaults_keep_alive_e_num_ctx() -> None:
    body = build_ollama_generate_payload("oi", model="qwen2.5-coder:3b", system="sys")
    assert body["keep_alive"] == "30m"
    assert body["options"]["num_ctx"] == 4096
    assert body["stream"] is False


def test_ollama_payload_lê_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "1h")
    monkeypatch.setenv("YBY_OLLAMA_NUM_CTX", "2048")
    body = build_ollama_generate_payload("p", model="m", system="s")
    assert body["keep_alive"] == "1h"
    assert body["options"]["num_ctx"] == 2048


def test_ollama_complete_envia_keep_alive_no_post(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "45m")
    monkeypatch.setenv("YBY_OLLAMA_NUM_CTX", "8192")
    session = _Session()
    OllamaProvider("http://127.0.0.1:11434", timeout=1, session=session).complete(
        "p",
        model="m",
        system="s",
    )
    payload = session.posts[0]["json"]
    assert isinstance(payload, dict)
    assert payload["keep_alive"] == "45m"
    assert payload["options"]["num_ctx"] == 8192


def test_cascade_falha_primario_sem_segundo_provedor() -> None:
    primary = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="or-key",
        timeout=1,
        session=_Session(error=requests.ConnectionError("down")),
    )
    chain = CascadingCloudProvider(primary, primary_model="openrouter/free")
    with pytest.raises(ProviderError, match="Nenhum segundo provedor"):
        chain.complete_with_meta("oi", system="sys")


def test_cascade_sucesso_primario() -> None:
    primary = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="or-key",
        timeout=1,
        session=_Session(
            _Resp(200, {"choices": [{"message": {"content": "or"}}]})
        ),
    )
    chain = CascadingCloudProvider(primary, primary_model="openrouter/free")
    result = chain.complete_with_meta("oi", system="sys")
    assert result.via == "openrouter"


def test_ollama_conexao_recusada_compativel() -> None:
    session = _Session(error=requests.ConnectionError("recusada"))
    provider = OllamaProvider("http://127.0.0.1:11434", timeout=1, session=session)
    with pytest.raises(ProviderUnreachable):
        provider.complete("oi", model="qwen2.5-coder:3b", system="sistema")
