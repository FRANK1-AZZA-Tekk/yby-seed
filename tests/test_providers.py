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
    assert body["options"]["num_predict"] == 1024
    # think:false no generate vaza markup; omitir o campo (ollama#18044).
    assert "think" not in body
    assert body["stream"] is False


def test_ollama_payload_lê_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "1h")
    monkeypatch.setenv("YBY_OLLAMA_NUM_CTX", "2048")
    monkeypatch.setenv("YBY_OLLAMA_NUM_PREDICT", "-1")
    monkeypatch.setenv("YBY_OLLAMA_THINK", "sim")
    body = build_ollama_generate_payload("p", model="m", system="s")
    assert body["keep_alive"] == "1h"
    assert body["options"]["num_ctx"] == 2048
    assert body["options"]["num_predict"] == -1
    assert body["think"] is True


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


def test_cascade_nao_chama_fallback_quando_primario_falha() -> None:
    primary = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="or-key",
        timeout=1,
        session=_Session(error=requests.ConnectionError("down")),
    )
    fallback = CloudProvider(
        "https://api.x.ai/v1",
        api_key="xai-key",
        timeout=1,
        session=_Session(),
    )
    chain = CascadingCloudProvider(
        primary,
        primary_model="openrouter/free",
        fallback=fallback,
        fallback_model="grok-4.7",
    )
    with pytest.raises(ProviderError, match="não é chamada automaticamente"):
        chain.complete_with_meta("oi", system="sys")
    assert fallback._session.posts == []  # type: ignore[attr-defined]


def test_cascade_sucesso_primario_nao_chama_fallback() -> None:
    primary = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="or-key",
        timeout=1,
        session=_Session(
            _Resp(200, {"choices": [{"message": {"content": "or"}}]})
        ),
    )
    fallback = CloudProvider(
        "https://api.x.ai/v1",
        api_key="xai-key",
        timeout=1,
        session=_Session(),
    )
    chain = CascadingCloudProvider(
        primary,
        primary_model="openrouter/free",
        fallback=fallback,
        fallback_model="grok-4.7",
    )
    result = chain.complete_with_meta("oi", system="sys")
    assert result.via == "openrouter"
    assert fallback._session.posts == []  # type: ignore[attr-defined]


def test_ollama_usa_thinking_quando_response_vem_vazio() -> None:
    session = _Session(_Resp(200, {"response": "", "thinking": "raciocinio util"}))
    text = OllamaProvider("http://127.0.0.1:11434", timeout=1, session=session).complete(
        "p",
        model="qwen3",
        system="s",
    )
    assert text == "raciocinio util"
    timeout = session.posts[0]["timeout"]
    assert timeout == (1, 1)


def test_ollama_remove_markup_think_vazado_em_response() -> None:
    session = _Session(
        _Resp(
            200,
            {
                "response": (
                    "<think>\npasso interno\n</think>\n"
                    "resposta limpa"
                ),
                "thinking": None,
            },
        )
    )
    text = OllamaProvider("http://127.0.0.1:11434", timeout=1, session=session).complete(
        "p",
        model="qwen3",
        system="s",
    )
    assert text == "resposta limpa"

    orphan = _Session(
        _Resp(
            200,
            {
                "response": "raciocinio solto\n</think>\nOK final",
                "thinking": None,
            },
        )
    )
    text = OllamaProvider("http://127.0.0.1:11434", timeout=1, session=orphan).complete(
        "p",
        model="qwen3",
        system="s",
    )
    assert text == "OK final"


def test_ollama_vazio_informa_done_reason() -> None:
    session = _Session(_Resp(200, {"response": "", "thinking": "", "done_reason": "length"}))
    provider = OllamaProvider("http://127.0.0.1:11434", timeout=12, session=session)
    with pytest.raises(ProviderError, match="done_reason=length"):
        provider.complete("p", model="qwen3", system="s")
    assert session.posts[0]["timeout"] == (5, 12)


def test_nuvem_aceita_content_em_lista_e_reasoning() -> None:
    listed = _Session(
        _Resp(
            200,
            {"choices": [{"message": {"content": [{"type": "text", "text": "da lista"}]}}]},
        )
    )
    provider = CloudProvider("https://openrouter.ai/api/v1", api_key="k", timeout=1, session=listed)
    assert provider.complete("oi", model="openrouter/free", system="s") == "da lista"

    reasoning = _Session(
        _Resp(
            200,
            {"choices": [{"message": {"content": None, "reasoning": "so o raciocinio"}}]},
        )
    )
    provider = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="k",
        timeout=1,
        session=reasoning,
    )
    assert provider.complete("oi", model="openrouter/free", system="s") == "so o raciocinio"


def test_nuvem_http_200_com_erro_e_retry_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.engine.providers.time.sleep", lambda _delay: None)
    erro = _Session(_Resp(200, {"error": {"message": "sem cota"}}))
    provider = CloudProvider("https://openrouter.ai/api/v1", api_key="k", timeout=1, session=erro)
    with pytest.raises(ProviderError, match="sem cota"):
        provider.complete("oi", model="openrouter/free", system="s")

    class _Flaky:
        def __init__(self) -> None:
            self.posts: list[dict[str, object]] = []
            self._n = 0

        def post(self, url: str, **kwargs: object) -> _Resp:
            self.posts.append({"url": url, **kwargs})
            self._n += 1
            if self._n == 1:
                return _Resp(503, {"error": "busy"})
            return _Resp(200, {"choices": [{"message": {"content": "depois"}}]})

    flaky = _Flaky()
    provider = CloudProvider("https://openrouter.ai/api/v1", api_key="k", timeout=1, session=flaky)
    assert provider.complete("oi", model="openrouter/free", system="s") == "depois"
    assert len(flaky.posts) == 2


def test_nuvem_retry_em_falha_de_conexao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.engine.providers.time.sleep", lambda _delay: None)

    class _FlakyConn:
        def __init__(self) -> None:
            self.posts: list[dict[str, object]] = []
            self._n = 0

        def post(self, url: str, **kwargs: object) -> _Resp:
            self.posts.append({"url": url, **kwargs})
            self._n += 1
            if self._n == 1:
                raise requests.ConnectionError("reset")
            return _Resp(200, {"choices": [{"message": {"content": "ok"}}]})

    flaky = _FlakyConn()
    provider = CloudProvider(
        "https://openrouter.ai/api/v1", api_key="k", timeout=1, session=flaky
    )
    assert provider.complete("oi", model="openrouter/free", system="s") == "ok"
    assert len(flaky.posts) == 2


def test_ollama_conexao_recusada_compativel() -> None:
    session = _Session(error=requests.ConnectionError("recusada"))
    provider = OllamaProvider("http://127.0.0.1:11434", timeout=1, session=session)
    with pytest.raises(ProviderUnreachable):
        provider.complete("oi", model="qwen2.5-coder:3b", system="sistema")


def test_ollama_retry_em_falha_de_conexao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.engine.providers.time.sleep", lambda _delay: None)

    class _FlakyConn:
        def __init__(self) -> None:
            self.posts: list[dict[str, object]] = []
            self._n = 0

        def post(self, url: str, **kwargs: object) -> _Resp:
            self.posts.append({"url": url, **kwargs})
            self._n += 1
            if self._n == 1:
                raise requests.ConnectionError("reset")
            return _Resp(200, {"response": "ok local"})

    flaky = _FlakyConn()
    provider = OllamaProvider("http://127.0.0.1:11434", timeout=1, session=flaky)
    assert provider.complete("oi", model="qwen2.5-coder:3b", system="s") == "ok local"
    assert len(flaky.posts) == 2
