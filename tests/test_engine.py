"""Roteamento e motor híbrido com Ollama e nuvem simulados."""

from __future__ import annotations

import pytest
import requests

from src.engine.cache import ResponseCache
from src.engine.config import (
    DEFAULT_CLOUD_BASE_URL,
    DEFAULT_CLOUD_MODEL,
    DEFAULT_LOCAL_MODEL,
    EngineConfig,
    EngineConfigError,
)
from src.engine.hybrid import HybridEngine
from src.engine.providers import (
    CascadingCloudProvider,
    CloudProvider,
    OllamaProvider,
    ProviderError,
    ProviderUnreachable,
)
from src.engine.routing import DEFAULT_HEAVY_PHRASES, decide_route


def _config(
    *,
    ollama_base_url: str = "http://ollama.test",
    local_model: str = "qwen2.5-coder:3b",
    cloud_base_url: str = "https://openrouter.ai/api/v1",
    cloud_model: str = "openrouter/free",
    cloud_api_key: str = "test-key",
    cloud_fallback_base_url: str = "https://api.x.ai/v1",
    cloud_fallback_model: str = "grok-4.7",
    cloud_fallback_api_key: str = "",
    heavy_min_chars: int = 1200,
    heavy_min_lines: int = 25,
    heavy_min_questions: int = 3,
    heavy_phrases: tuple[str, ...] = DEFAULT_HEAVY_PHRASES,
    ollama_timeout: float = 5.0,
    cloud_timeout: float = 5.0,
    cache_ttl_seconds: float = 0.0,
    cloud_max_chars: int = 12000,
) -> EngineConfig:
    return EngineConfig(
        ollama_base_url=ollama_base_url,
        local_model=local_model,
        cloud_base_url=cloud_base_url,
        cloud_model=cloud_model,
        cloud_api_key=cloud_api_key,
        cloud_fallback_base_url=cloud_fallback_base_url,
        cloud_fallback_model=cloud_fallback_model,
        cloud_fallback_api_key=cloud_fallback_api_key,
        heavy_min_chars=heavy_min_chars,
        heavy_min_lines=heavy_min_lines,
        heavy_min_questions=heavy_min_questions,
        heavy_phrases=heavy_phrases,
        ollama_timeout=ollama_timeout,
        cloud_timeout=cloud_timeout,
        cache_ttl_seconds=cache_ttl_seconds,
        cloud_max_chars=cloud_max_chars,
    )


class FakeOllama:
    def __init__(self, text: str = "resposta-local", error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls: list[dict[str, str]] = []

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        self.calls.append({"prompt": prompt, "model": model, "system": system})
        if self.error:
            raise self.error
        return self.text


class FakeCloud:
    def __init__(
        self,
        text: str = "resposta-nuvem",
        *,
        api_key: str = "test-key",
        error: Exception | None = None,
    ) -> None:
        self.text = text
        self.api_key = api_key
        self.error = error
        self.calls: list[dict[str, str]] = []

    def has_credentials(self) -> bool:
        return bool(self.api_key)

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        self.calls.append({"prompt": prompt, "model": model, "system": system})
        if self.error:
            raise self.error
        return self.text


def _route(
    prompt: str,
    *,
    heavy_min_chars: int = 1200,
    heavy_phrases: tuple[str, ...] = DEFAULT_HEAVY_PHRASES,
) -> str:
    config = _config(heavy_min_chars=heavy_min_chars, heavy_phrases=heavy_phrases)
    decision = decide_route(
        prompt,
        explicit_heavy=False,
        heavy_min_chars=config.heavy_min_chars,
        heavy_min_lines=config.heavy_min_lines,
        heavy_min_questions=config.heavy_min_questions,
        heavy_phrases=config.heavy_phrases,
    )
    return decision.target


def test_pedido_curto_fica_local() -> None:
    decision = decide_route(
        "explica uma lista",
        explicit_heavy=False,
        heavy_min_chars=1200,
        heavy_min_lines=25,
        heavy_min_questions=3,
        heavy_phrases=DEFAULT_HEAVY_PHRASES,
    )
    assert decision.target == "local"
    assert decision.reasons == ("pedido dentro do limite local",)


def test_frase_pensa_mais_vai_para_nuvem() -> None:
    decision = decide_route(
        "Pensa mais sobre recursão",
        explicit_heavy=False,
        heavy_min_chars=1200,
        heavy_min_lines=25,
        heavy_min_questions=3,
        heavy_phrases=DEFAULT_HEAVY_PHRASES,
    )
    assert decision.target == "cloud"
    assert "frase explícita: pensa mais" in decision.reasons


def test_frase_parecida_nao_dispara() -> None:
    assert _route("pensei mais cedo em outra coisa") == "local"


def test_flag_heavy_e_registrada() -> None:
    decision = decide_route(
        "oi",
        explicit_heavy=True,
        heavy_min_chars=1200,
        heavy_min_lines=25,
        heavy_min_questions=3,
        heavy_phrases=DEFAULT_HEAVY_PHRASES,
    )
    assert decision.target == "cloud"
    assert decision.reasons == ("flag --heavy",)


@pytest.mark.parametrize(
    ("prompt", "reason_part"),
    [
        ("a" * 1200, "caracteres"),
        ("\n".join(["linha"] * 25), "linhas"),
        ("um? dois? três?", "perguntas"),
    ],
)
def test_limiares_de_tamanho_e_complexidade(prompt: str, reason_part: str) -> None:
    decision = decide_route(
        prompt,
        explicit_heavy=False,
        heavy_min_chars=1200,
        heavy_min_lines=25,
        heavy_min_questions=3,
        heavy_phrases=DEFAULT_HEAVY_PHRASES,
    )
    assert decision.target == "cloud"
    assert any(reason_part in reason for reason in decision.reasons)


def test_limiares_configuraveis() -> None:
    assert _route("abcd", heavy_min_chars=4) == "cloud"
    assert _route("oi", heavy_min_chars=4) == "local"
    assert _route("usa o modo turbo", heavy_phrases=("modo turbo",)) == "cloud"


def test_modelo_local_padrao_e_o_vencedor_do_benchmark() -> None:
    config = EngineConfig.from_env({})
    assert config.local_model == DEFAULT_LOCAL_MODEL == "qwen2.5-coder:3b"
    assert config.cloud_base_url == DEFAULT_CLOUD_BASE_URL == "https://openrouter.ai/api/v1"
    assert config.cloud_model == DEFAULT_CLOUD_MODEL == "openrouter/free"
    assert config.cloud_api_key == ""
    assert config.cloud_fallback_base_url == "https://api.x.ai/v1"
    assert config.cloud_fallback_model == "grok-4.7"
    assert config.cloud_fallback_api_key == ""


def test_from_env_le_chave_e_limiares() -> None:
    config = EngineConfig.from_env(
        {
            "YBY_LOCAL_MODEL": "outro:3b",
            "YBY_CLOUD_API_KEY": "chave-yby",
            "OPENROUTER_API_KEY": "chave-or",
            "XAI_API_KEY": "chave-xai",
            "YBY_HEAVY_MIN_CHARS": "10",
            "YBY_HEAVY_MIN_LINES": "2",
            "YBY_HEAVY_MIN_QUESTIONS": "1",
            "YBY_CLOUD_MODEL": "meu/free",
            "YBY_CLOUD_BASE_URL": "https://example.test/v1",
            "YBY_OLLAMA_BASE_URL": "http://10.0.0.2:11434",
            "YBY_CACHE_TTL_SECONDS": "90",
            "YBY_CLOUD_CONTEXT_MAX_CHARS": "500",
        }
    )
    assert config.local_model == "outro:3b"
    assert config.cloud_api_key == "chave-yby"
    assert config.cloud_model == "meu/free"
    assert config.cloud_base_url == "https://example.test/v1"
    assert config.cloud_fallback_api_key == "chave-xai"
    assert config.ollama_base_url == "http://10.0.0.2:11434"
    assert config.heavy_min_chars == 10
    assert config.heavy_min_lines == 2
    assert config.heavy_min_questions == 1
    assert config.cache_ttl_seconds == 90
    assert config.cloud_max_chars == 500


def test_from_env_aceita_openrouter_e_xai_como_aliases() -> None:
    config = EngineConfig.from_env(
        {
            "OPENROUTER_API_KEY": "chave-or",
            "XAI_API_KEY": "chave-xai",
        }
    )
    assert config.cloud_api_key == "chave-or"
    assert config.cloud_fallback_api_key == "chave-xai"


def test_from_env_rejeita_limiar_invalido() -> None:
    with pytest.raises(EngineConfigError):
        EngineConfig.from_env({"YBY_HEAVY_MIN_CHARS": "muitos"})


def test_resposta_curta_usa_ollama_e_nao_chama_nuvem() -> None:
    ollama = FakeOllama()
    cloud = FakeCloud()
    reply = HybridEngine(_config(), ollama, cloud, cache=ResponseCache(ttl_seconds=0)).reply(
        "explica uma lista"
    )

    assert reply.provider == "local"
    assert reply.model == "qwen2.5-coder:3b"
    assert reply.text == "resposta-local"
    assert reply.notice is None
    assert ollama.calls[0]["model"] == "qwen2.5-coder:3b"
    assert cloud.calls == []


def test_ollama_fora_cai_na_nuvem() -> None:
    ollama = FakeOllama(error=ProviderUnreachable("conexão recusada"))
    cloud = FakeCloud()
    reply = HybridEngine(_config(), ollama, cloud, cache=ResponseCache(ttl_seconds=0)).reply("oi")

    assert reply.provider == "cloud"
    assert reply.model == "openrouter/free"
    assert reply.text == "resposta-nuvem"
    assert reply.notice is not None
    assert "Ollama falhou" in reply.notice
    assert "openrouter/free" in reply.notice


def test_ollama_fora_sem_chave_explica_o_bloqueio() -> None:
    ollama = FakeOllama(error=ProviderUnreachable("conexão recusada"))
    cloud = FakeCloud(api_key="")
    reply = HybridEngine(
        _config(cloud_api_key=""), ollama, cloud, cache=ResponseCache(ttl_seconds=0)
    ).reply("oi")

    assert reply.provider == "none"
    assert reply.text == ""
    assert reply.notice is not None
    assert "YBY_CLOUD_API_KEY" in reply.notice
    assert cloud.calls == []


def test_heavy_sem_chave_degrada_para_o_local() -> None:
    ollama = FakeOllama()
    cloud = FakeCloud(api_key="")
    reply = HybridEngine(
        _config(cloud_api_key=""), ollama, cloud, cache=ResponseCache(ttl_seconds=0)
    ).reply("oi", explicit_heavy=True)

    assert reply.provider == "local"
    assert reply.model == "qwen2.5-coder:3b"
    assert reply.notice is not None
    assert "YBY_CLOUD_API_KEY" in reply.notice
    assert "qwen2.5-coder:3b" in reply.notice
    assert cloud.calls == []


def test_heavy_sem_chave_e_sem_ollama() -> None:
    ollama = FakeOllama(error=ProviderUnreachable("down"))
    cloud = FakeCloud(api_key="")
    reply = HybridEngine(
        _config(cloud_api_key=""), ollama, cloud, cache=ResponseCache(ttl_seconds=0)
    ).reply(
        "pensa mais",
        explicit_heavy=True,
    )

    assert reply.provider == "none"
    assert reply.notice is not None
    assert "YBY_CLOUD_API_KEY" in reply.notice
    assert "Ollama também falhou" in reply.notice


def test_heavy_com_chave_nao_chama_ollama() -> None:
    ollama = FakeOllama()
    cloud = FakeCloud()
    reply = HybridEngine(_config(), ollama, cloud, cache=ResponseCache(ttl_seconds=0)).reply(
        "pensa mais sobre isso"
    )

    assert reply.provider == "cloud"
    assert reply.text == "resposta-nuvem"
    assert ollama.calls == []
    assert cloud.calls[0]["model"] == "openrouter/free"


def test_nuvem_fora_volta_ao_local() -> None:
    ollama = FakeOllama()
    cloud = FakeCloud(error=ProviderError("HTTP 503"))
    reply = HybridEngine(_config(), ollama, cloud, cache=ResponseCache(ttl_seconds=0)).reply(
        "a" * 1200
    )

    assert reply.provider == "local"
    assert reply.notice is not None
    assert "Nuvem falhou" in reply.notice


def test_contexto_e_truncado_antes_da_nuvem() -> None:
    ollama = FakeOllama()
    cloud = FakeCloud()
    prompt = "pensa mais " + ("x" * 200)
    reply = HybridEngine(
        _config(cloud_max_chars=40),
        ollama,
        cloud,
        cache=ResponseCache(ttl_seconds=0),
    ).reply(prompt)

    assert reply.provider == "cloud"
    sent = cloud.calls[0]["prompt"]
    assert len(sent) <= 40
    assert "truncado" in sent


class _Response:
    def __init__(self, status: int, payload: object) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> object:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _Session:
    def __init__(self, response: _Response | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.posts: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> _Response:
        self.posts.append({"url": url, **kwargs})
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


def test_ollama_provider_envia_o_modelo_recebido() -> None:
    session = _Session(_Response(200, {"response": "ok"}))
    provider = OllamaProvider("http://127.0.0.1:11434", timeout=3, session=session)
    text = provider.complete("oi", model="qwen2.5-coder:3b", system="sistema")

    assert text == "ok"
    body = session.posts[0]["json"]
    assert isinstance(body, dict)
    assert body["model"] == "qwen2.5-coder:3b"
    assert body["stream"] is False
    assert session.posts[0]["url"] == "http://127.0.0.1:11434/api/generate"


def test_ollama_provider_trata_conexao_recusada() -> None:
    session = _Session(error=requests.ConnectionError("recusada"))
    provider = OllamaProvider("http://127.0.0.1:11434", timeout=3, session=session)
    with pytest.raises(ProviderUnreachable):
        provider.complete("oi", model="qwen2.5-coder:3b", system="sistema")


def test_cloud_provider_usa_bearer_e_nao_chama_sem_chave() -> None:
    session = _Session()
    provider = CloudProvider(
        "https://openrouter.ai/api/v1/",
        api_key="",
        timeout=3,
        session=session,
    )
    with pytest.raises(ProviderError, match="YBY_CLOUD_API_KEY"):
        provider.complete("oi", model="openrouter/free", system="sistema")
    assert session.posts == []

    session = _Session(
        _Response(200, {"choices": [{"message": {"content": "da nuvem"}}]}),
    )
    provider = CloudProvider(
        "https://openrouter.ai/api/v1/",
        api_key="segredo",
        timeout=3,
        session=session,
    )
    assert provider.complete("oi", model="openrouter/free", system="sistema") == "da nuvem"
    headers = session.posts[0]["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer segredo"
    assert session.posts[0]["url"] == "https://openrouter.ai/api/v1/chat/completions"
    body = session.posts[0]["json"]
    assert isinstance(body, dict)
    assert body["model"] == "openrouter/free"


def test_cascading_openrouter_falha_sem_fallback_automatico() -> None:
    primary = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="or",
        timeout=3,
        session=_Session(error=requests.ConnectionError("or-down")),
    )
    fallback = CloudProvider(
        "https://api.x.ai/v1",
        api_key="xai",
        timeout=3,
        session=_Session(
            _Response(200, {"choices": [{"message": {"content": "via-grok"}}]}),
        ),
    )
    chain = CascadingCloudProvider(
        primary,
        primary_model="openrouter/free",
        fallback=fallback,
        fallback_model="grok-4.7",
    )
    with pytest.raises(ProviderError, match="não é chamada automaticamente"):
        chain.complete_with_meta("oi", system="sys")
    assert fallback._session.posts == []


def test_cascading_usa_openrouter_quando_ok() -> None:
    primary = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="or",
        timeout=3,
        session=_Session(
            _Response(200, {"choices": [{"message": {"content": "via-or"}}]}),
        ),
    )
    fallback = CloudProvider(
        "https://api.x.ai/v1",
        api_key="xai",
        timeout=3,
        session=_Session(),
    )
    chain = CascadingCloudProvider(
        primary,
        primary_model="openrouter/free",
        fallback=fallback,
        fallback_model="grok-4.7",
    )
    result = chain.complete_with_meta("oi", system="sys")
    assert result.text == "via-or"
    assert result.via == "openrouter"
    assert fallback._session.posts == []  # type: ignore[attr-defined]


def test_cascading_sem_openrouter_nao_usa_grok_automaticamente() -> None:
    primary = CloudProvider("https://openrouter.ai/api/v1", api_key="", timeout=3)
    fallback = CloudProvider(
        "https://api.x.ai/v1",
        api_key="xai",
        timeout=3,
        session=_Session(
            _Response(200, {"choices": [{"message": {"content": "via-grok"}}]}),
        ),
    )
    chain = CascadingCloudProvider(
        primary,
        primary_model="openrouter/free",
        fallback=fallback,
        fallback_model="grok-4.7",
    )
    assert chain.has_credentials() is False
    with pytest.raises(ProviderError, match="YBY_CLOUD_API_KEY"):
        chain.complete_with_meta("oi", system="sys")


def test_motor_com_openrouter_falho_nao_cai_no_grok() -> None:
    ollama = FakeOllama()
    primary = FakeCloud(api_key="or", error=ProviderError("HTTP 429"))
    fallback = FakeCloud(text="via-grok", api_key="xai")
    chain = CascadingCloudProvider(
        primary,  # type: ignore[arg-type]
        primary_model="openrouter/free",
        fallback=fallback,  # type: ignore[arg-type]
        fallback_model="grok-4.7",
    )
    reply = HybridEngine(
        _config(),
        ollama,
        chain,
        cloud_chain=chain,
        cache=ResponseCache(ttl_seconds=0),
    ).reply("pensa mais")
    assert reply.provider == "local"
    assert reply.text == "resposta-local"
    assert reply.notice is not None
    assert "não é chamada automaticamente" in reply.notice
    assert fallback.calls == []
