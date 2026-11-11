"""OpenRouter→Grok, cache TTL e limite de contexto (HTTP mockado)."""

from __future__ import annotations

import time

import pytest
import requests

from src.engine.cache import ResponseCache
from src.engine.config import DEFAULT_CLOUD_MODEL, EngineConfig
from src.engine.context import trim_context
from src.engine.hybrid import HybridEngine
from src.engine.providers import CascadingCloudProvider, CloudProvider, ProviderError
from src.engine.routing import DEFAULT_HEAVY_PHRASES


def _config(**overrides: object) -> EngineConfig:
    base = dict(
        ollama_base_url="http://ollama.test",
        local_model="qwen2.5-coder:3b",
        cloud_base_url="https://openrouter.ai/api/v1",
        cloud_model=DEFAULT_CLOUD_MODEL,
        cloud_api_key="or-key",
        cloud_fallback_base_url="https://api.x.ai/v1",
        cloud_fallback_model="grok-4.7",
        cloud_fallback_api_key="xai-key",
        heavy_min_chars=1200,
        heavy_min_lines=25,
        heavy_min_questions=3,
        heavy_phrases=DEFAULT_HEAVY_PHRASES,
        ollama_timeout=5.0,
        cloud_timeout=5.0,
        cache_ttl_seconds=3600.0,
        cloud_max_chars=12000,
    )
    base.update(overrides)
    return EngineConfig(**base)  # type: ignore[arg-type]


class FakeOllama:
    def __init__(self, text: str = "local") -> None:
        self.text = text
        self.calls: list[dict[str, str]] = []

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        self.calls.append({"prompt": prompt, "model": model, "system": system})
        return self.text


class _Response:
    def __init__(self, status: int, payload: object) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> object:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _Session:
    def __init__(self, responses: list[_Response | Exception]) -> None:
        self._responses = list(responses)
        self.posts: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> _Response:
        self.posts.append({"url": url, **kwargs})
        if not self._responses:
            raise AssertionError("sem respostas mock restantes")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_from_env_padrao_openrouter_free_e_grok_fallback() -> None:
    config = EngineConfig.from_env({})
    assert config.cloud_base_url == "https://openrouter.ai/api/v1"
    assert config.cloud_model == "openrouter/free"
    assert config.cloud_fallback_base_url == "https://api.x.ai/v1"
    assert config.cloud_fallback_model == "grok-4.7"
    assert config.cache_ttl_seconds == 3600.0
    assert config.cloud_max_chars == 12000


def test_from_env_le_openrouter_e_grok_aliases() -> None:
    config = EngineConfig.from_env(
        {
            "OPENROUTER_API_KEY": "or-secret",
            "YBY_GROK_API_KEY": "grok-secret",
            "YBY_GROK_MODEL": "grok-custom",
            "YBY_CLOUD_CONTEXT_MAX_CHARS": "500",
            "YBY_CACHE_TTL_SECONDS": "10",
        }
    )
    assert config.cloud_api_key == "or-secret"
    assert config.cloud_fallback_api_key == "grok-secret"
    assert config.cloud_fallback_model == "grok-custom"
    assert config.cloud_max_chars == 500
    assert config.cache_ttl_seconds == 10.0


def test_openrouter_falha_cai_no_grok_http_mock() -> None:
    openrouter = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="or-key",
        timeout=3,
        session=_Session([_Response(503, {"error": "busy"})]),
    )
    grok = CloudProvider(
        "https://api.x.ai/v1",
        api_key="xai-key",
        timeout=3,
        session=_Session(
            [_Response(200, {"choices": [{"message": {"content": "via grok"}}]})]
        ),
    )
    chain = CascadingCloudProvider(
        openrouter,
        primary_model="openrouter/free",
        fallback=grok,
        fallback_model="grok-4.7",
    )
    result = chain.complete_with_meta("pensa mais", system="sys")
    assert result.text == "via grok"
    assert result.model == "grok-4.7"
    assert result.via == "grok"


def test_openrouter_ok_nao_chama_grok() -> None:
    openrouter_session = _Session(
        [_Response(200, {"choices": [{"message": {"content": "via or"}}]})]
    )
    grok_session = _Session([])
    chain = CascadingCloudProvider(
        CloudProvider(
            "https://openrouter.ai/api/v1",
            api_key="or-key",
            timeout=3,
            session=openrouter_session,
        ),
        primary_model="openrouter/free",
        fallback=CloudProvider(
            "https://api.x.ai/v1",
            api_key="xai-key",
            timeout=3,
            session=grok_session,
        ),
        fallback_model="grok-4.7",
    )
    result = chain.complete_with_meta("pensa mais", system="sys")
    assert result.via == "openrouter"
    assert result.model == "openrouter/free"
    assert grok_session.posts == []


def test_cascade_sem_credenciais_explica() -> None:
    chain = CascadingCloudProvider(
        CloudProvider("https://openrouter.ai/api/v1", api_key="", timeout=3),
        primary_model="openrouter/free",
        fallback=CloudProvider("https://api.x.ai/v1", api_key="", timeout=3),
        fallback_model="grok-4.7",
    )
    assert chain.has_credentials() is False
    with pytest.raises(ProviderError, match="YBY_CLOUD_API_KEY"):
        chain.complete("oi", model="x", system="sys")


def test_cache_ttl_hit_e_expira() -> None:
    cache = ResponseCache(ttl_seconds=0.05)
    key = cache.make_key("prompt", model="m", system="s")
    assert cache.get(key) is None
    cache.set(key, "cached")
    assert cache.get(key) == "cached"
    time.sleep(0.06)
    assert cache.get(key) is None


def test_cache_ttl_zero_desliga() -> None:
    cache = ResponseCache(ttl_seconds=0)
    key = cache.make_key("p", model="m", system="s")
    cache.set(key, "x")
    assert cache.get(key) is None


def test_motor_usa_cache_na_segunda_chamada_nuvem() -> None:
    session = _Session(
        [_Response(200, {"choices": [{"message": {"content": "nuvem-1"}}]})]
    )
    primary = CloudProvider(
        "https://openrouter.ai/api/v1", api_key="or-key", timeout=3, session=session
    )
    chain = CascadingCloudProvider(primary, primary_model="openrouter/free")
    engine = HybridEngine(
        _config(cache_ttl_seconds=60.0),
        FakeOllama(),
        chain,
        cloud_chain=chain,
        cache=ResponseCache(ttl_seconds=60.0),
    )
    first = engine.reply("pensa mais sobre listas")
    second = engine.reply("pensa mais sobre listas")
    assert first.text == "nuvem-1"
    assert second.text == "nuvem-1"
    assert second.model == "openrouter/free"
    assert len(session.posts) == 1


def test_contexto_truncado_antes_da_nuvem() -> None:
    session = _Session(
        [_Response(200, {"choices": [{"message": {"content": "ok"}}]})]
    )
    primary = CloudProvider(
        "https://openrouter.ai/api/v1", api_key="or-key", timeout=3, session=session
    )
    chain = CascadingCloudProvider(primary, primary_model="openrouter/free")
    long_prompt = "pensa mais " + ("x" * 500)
    engine = HybridEngine(
        _config(cloud_max_chars=80, cache_ttl_seconds=0),
        FakeOllama(),
        chain,
        cloud_chain=chain,
        cache=ResponseCache(ttl_seconds=0),
    )
    reply = engine.reply(long_prompt)
    assert reply.provider == "cloud"
    body = session.posts[0]["json"]
    assert isinstance(body, dict)
    user_msg = body["messages"][1]["content"]
    assert isinstance(user_msg, str)
    assert len(user_msg) <= 80
    assert "truncado" in user_msg


def test_trim_context_preserva_curto() -> None:
    assert trim_context("oi", 100) == "oi"


def test_trim_context_corta_longo() -> None:
    text = "A" * 100 + "MEIO" + "B" * 100
    out = trim_context(text, 40)
    assert len(out) == 40
    assert "truncado" in out


def test_conexao_recusada_no_openrouter_tenta_grok() -> None:
    openrouter = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="or-key",
        timeout=3,
        session=_Session([requests.ConnectionError("down")]),
    )
    grok = CloudProvider(
        "https://api.x.ai/v1",
        api_key="xai-key",
        timeout=3,
        session=_Session(
            [_Response(200, {"choices": [{"message": {"content": "grok ok"}}]})]
        ),
    )
    chain = CascadingCloudProvider(
        openrouter,
        primary_model="openrouter/free",
        fallback=grok,
        fallback_model="grok-4.7",
    )
    assert chain.complete("pensa mais", model="x", system="s") == "grok ok"
