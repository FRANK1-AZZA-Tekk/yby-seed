"""Testes offline do YBY Machine (Spec-First). Sem rede."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.engine.providers import ProviderError
from src.yby_machine.cache import SpecFingerprintCache, prompt_fingerprint
from src.yby_machine.compiler import compile_pwa, write_pwa
from src.yby_machine.fallback import fallback_spec_from_prompt
from src.yby_machine.http import create_app
from src.yby_machine.spec import (
    BrFieldType,
    PaymentStatus,
    PixConfig,
    WhatsAppConfig,
    YBYSpec,
    yby_spec_json_schema,
)
from src.yby_machine.translator import (
    TranslateResult,
    parse_spec_json,
    prompt_to_spec,
    prompt_to_spec_result,
)

# Três cenários BR do MVP
_ENCOMENDA = "App de encomendas com Pix estático e botão WhatsApp wa.me"
_OFICINA = "Oficina mecânica com ordem de serviço OS e pagamento"
_ESTOQUE = "Controle de estoque simples de produtos e preços"


def test_fallback_encomenda_pix() -> None:
    spec = fallback_spec_from_prompt(_ENCOMENDA)
    assert spec.name == "encomendas"
    types = {f.type for e in spec.entities for f in e.fields}
    assert BrFieldType.moeda_brl in types
    assert BrFieldType.cpf in types or BrFieldType.telefone_br in types
    assert spec.pix.enabled is True
    assert spec.pix.payload
    assert PaymentStatus.pago in spec.payment_statuses
    assert PaymentStatus.pendente_fiado in spec.payment_statuses
    assert PaymentStatus.sinal_50 in spec.payment_statuses
    assert spec.whatsapp.enabled is True


def test_fallback_oficina_os() -> None:
    spec = fallback_spec_from_prompt(_OFICINA)
    assert spec.name == "oficina_os"
    assert any(r.result_field == "total" for r in spec.calc_rules)
    assert spec.pix.enabled is True


def test_fallback_estoque_simples() -> None:
    spec = fallback_spec_from_prompt(_ESTOQUE)
    assert spec.name == "estoque_simples"
    types = {f.type for e in spec.entities for f in e.fields}
    assert BrFieldType.cnpj in types
    assert BrFieldType.numero in types
    assert any(r.expression == "qtd * preco" for r in spec.calc_rules)


@pytest.mark.parametrize("prompt", [_ENCOMENDA, _OFICINA, _ESTOQUE])
def test_compiler_bundle_valid_syntax(prompt: str, tmp_path: Path) -> None:
    spec = fallback_spec_from_prompt(prompt)
    bundle = compile_pwa(spec)
    required = {"index.html", "styles.css", "app.js", "manifest.webmanifest", "sw.js", "spec.json"}
    assert required <= set(bundle.keys())

    html = bundle["index.html"]
    assert "<!DOCTYPE html>" in html
    assert "styles.css" in html
    assert "app.js" in html
    assert 'lang="pt-BR"' in html
    assert "Content-Security-Policy" in html
    assert "default-src 'self'" in html
    assert "#00FF66" in bundle["styles.css"]
    assert "#0D0D0D" in bundle["styles.css"]
    assert "#F5F5F2" in bundle["styles.css"]

    # JS não pode quebrar: JSON embutido parseável + estrutura básica
    assert "EMBEDDED_SPEC" in bundle["app.js"]
    assert "localStorage" in bundle["app.js"]
    assert "wa.me" in bundle["app.js"]
    assert "toLocaleString" in bundle["app.js"]
    assert "BRL" in bundle["app.js"]
    assert "yby-machine-v2" in bundle["sw.js"]
    manifest = json.loads(bundle["manifest.webmanifest"])
    assert manifest["name"] == spec.title
    assert manifest["display"] == "standalone"
    embedded = json.loads(bundle["spec.json"])
    YBYSpec.model_validate(embedded)

    # app.js: o objeto EMBEDDED_SPEC deve ser JSON válido (extrair literal)
    js = bundle["app.js"]
    start = js.index("const EMBEDDED_SPEC = ") + len("const EMBEDDED_SPEC = ")
    end = js.index(";\n  const STORAGE_KEY", start)
    json.loads(js[start:end])

    out = write_pwa(spec, str(tmp_path / "app"))
    assert (tmp_path / "app" / "index.html").is_file()
    assert len(out) == len(bundle)


def test_translator_mocked_ollama_success() -> None:
    spec = fallback_spec_from_prompt(_ENCOMENDA)
    raw = json.dumps(spec.model_dump(mode="json"), ensure_ascii=False)
    provider = MagicMock()
    provider.complete.return_value = raw

    result = asyncio.run(prompt_to_spec_result("pedido customizado", provider=provider))
    assert result.source == "ollama"
    assert result.spec.name == spec.name
    provider.complete.assert_called_once()
    kwargs = provider.complete.call_args.kwargs
    assert kwargs.get("ollama_format") == "json"
    system = kwargs.get("system") or ""
    assert "JSON Schema YBYSpec" in system
    assert '"title":"YBYSpec"' in system or '"title": "YBYSpec"' in system


def test_translator_mocked_failure_uses_fallback() -> None:
    provider = MagicMock()
    provider.complete.side_effect = ProviderError("Ollama offline")

    result = asyncio.run(
        prompt_to_spec_result(_OFICINA, provider=provider, use_fallback_on_error=True)
    )
    assert result.source == "fallback"
    assert result.spec.name == "oficina_os"


def test_translator_parse_incomplete_raises_or_fallback() -> None:
    with pytest.raises((ValueError, Exception)):
        parse_spec_json("{not json")

    provider = MagicMock()
    provider.complete.return_value = '{"title": "X"}'  # sem entities
    result = asyncio.run(prompt_to_spec_result("estoque de produtos", provider=provider))
    assert result.source == "fallback"
    assert result.spec.name == "estoque_simples"


def test_http_generate_with_mocked_translator(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = fallback_spec_from_prompt(_ENCOMENDA)

    async def _fake(prompt: str, **_kwargs):  # noqa: ANN001
        assert "encomenda" in prompt.casefold() or "Pix" in prompt or prompt
        return TranslateResult(spec, "fallback")

    monkeypatch.setattr("src.yby_machine.http.prompt_to_spec_result", _fake)
    client = TestClient(create_app())
    resp = client.post("/api/machine/generate", json={"prompt": _ENCOMENDA})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "fallback"
    assert body["spec"]["name"] == "encomendas"
    assert "index.html" in body["files"]
    assert "app.js" in body["files"]
    assert "Content-Security-Policy" in body["files"]["index.html"]
    health = client.get("/health")
    assert health.status_code == 200
    schema_resp = client.get("/api/machine/schema")
    assert schema_resp.status_code == 200
    assert schema_resp.json()["title"] == "YBYSpec"


def test_prompt_to_spec_empty_fallback() -> None:
    spec = asyncio.run(prompt_to_spec("", use_fallback_on_error=True))
    assert isinstance(spec, YBYSpec)
    assert spec.entities


def test_yby_spec_json_schema_export() -> None:
    schema = yby_spec_json_schema()
    assert schema["title"] == "YBYSpec"
    assert "properties" in schema
    assert "entities" in schema["properties"]
    defs = schema.get("$defs") or schema.get("definitions") or {}
    assert "BrFieldType" in defs or "PixConfig" in defs


def test_pix_and_phone_validators() -> None:
    with pytest.raises(ValidationError):
        PixConfig(enabled=True, payload="")
    with pytest.raises(ValidationError):
        PixConfig(enabled=True, payload="nao-e-br-code")
    ok = PixConfig(enabled=True, payload="00020126580014BR.GOV.BCB.PIX0136abc")
    assert ok.payload.startswith("000201")

    with pytest.raises(ValidationError):
        WhatsAppConfig(phone_e164="123")
    assert WhatsAppConfig(phone_e164="+5511987654321").phone_e164 == "+5511987654321"
    assert WhatsAppConfig(phone_e164="").phone_e164 == ""


def test_spec_fingerprint_cache() -> None:
    cache = SpecFingerprintCache(max_size=2)
    spec = fallback_spec_from_prompt(_ENCOMENDA)
    first = TranslateResult(spec, "fallback")
    cache.put(_ENCOMENDA, first)
    assert cache.get(_ENCOMENDA) is first
    assert cache.get("  " + _ENCOMENDA.upper() + "  ") is first
    assert prompt_fingerprint(_ENCOMENDA) == prompt_fingerprint("  " + _ENCOMENDA.upper())

    provider = MagicMock()
    provider.complete.side_effect = ProviderError("offline")
    result1 = asyncio.run(
        prompt_to_spec_result(_OFICINA, provider=provider, cache=cache)
    )
    assert result1.source == "fallback"
    provider.complete.assert_called_once()

    provider2 = MagicMock()
    provider2.complete.side_effect = AssertionError("não deve chamar")
    result2 = asyncio.run(
        prompt_to_spec_result(_OFICINA, provider=provider2, cache=cache)
    )
    assert result2.spec.name == result1.spec.name
    provider2.complete.assert_not_called()


def test_html_escapes_title_xss() -> None:
    spec = fallback_spec_from_prompt(_ESTOQUE)
    dirty = spec.model_copy(update={"title": '<script>alert(1)</script> & "x"'})
    html = compile_pwa(dirty)["index.html"]
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html
    assert "&quot;" in html


def test_compiler_hardening_idb_fallback_safe_dom_pix_wa_csp() -> None:
    spec = fallback_spec_from_prompt(_ENCOMENDA)
    bundle = compile_pwa(spec)
    html = bundle["index.html"]
    js = bundle["app.js"]

    assert "Content-Security-Policy" in html
    assert "default-src 'self'" in html
    assert "script-src 'self'" in html
    assert "IndexedDB + localStorage" in html

    assert "indexedDB" in js
    assert "IDB_STORE" in js
    assert "loadLocalStorage" in js
    assert "saveLocalStorage" in js
    assert "innerHTML" not in js
    assert "copyPixPayload" in js
    assert "000201" in js
    assert "https://wa.me/" in js
    assert "noopener noreferrer" in js


def test_pipeline_reuse_gate_threshold_092() -> None:
    from src.yby_machine.cache import AsyncSpecFingerprintCache
    from src.yby_machine.pipeline import MachinePipeline
    from src.yby_machine.store import InMemorySpecStore

    class _FakeEmbedder:
        def __init__(self, vectors: dict[str, list[float]]) -> None:
            self._vectors = vectors

        async def embed(self, text: str) -> list[float]:
            return list(self._vectors[text])

        async def close(self) -> None:
            return None

    # cos([1, 0], [0.95, 0.31225]) ~= 0.95 >= 0.92; cos([1, 0], [0.80, 0.60]) = 0.80 < 0.92
    embedder = _FakeEmbedder(
        {
            "app encomenda original": [1.0, 0.0],
            "app encomenda muito parecido": [0.95, 0.31225],
            "app oficina diferente": [0.80, 0.60],
        }
    )
    calls: list[str] = []

    async def _translator(prompt: str) -> TranslateResult:
        calls.append(prompt)
        return TranslateResult(fallback_spec_from_prompt(prompt), "ollama")

    pipeline = MachinePipeline(
        embedder=embedder,
        store=InMemorySpecStore(),
        cache=AsyncSpecFingerprintCache(),
        translator=_translator,
        min_similarity=0.92,
    )

    first = asyncio.run(pipeline.generate("app encomenda original"))
    assert first.source == "ollama"
    assert len(calls) == 1

    reused = asyncio.run(pipeline.generate("app encomenda muito parecido"))
    assert reused.source == "reuse"
    assert reused.app_id == first.app_id
    assert reused.similarity is not None and reused.similarity >= 0.92
    assert len(calls) == 1

    miss = asyncio.run(pipeline.generate("app oficina diferente"))
    assert miss.source == "ollama"
    assert miss.app_id != first.app_id
    assert len(calls) == 2


def test_pipeline_cache_hit_when_store_misses() -> None:
    from src.yby_machine.cache import AsyncSpecFingerprintCache
    from src.yby_machine.embedder import OfflineHashEmbedder
    from src.yby_machine.pipeline import MachinePipeline
    from src.yby_machine.store import InMemorySpecStore

    cache = AsyncSpecFingerprintCache()
    cached_spec = fallback_spec_from_prompt(_ESTOQUE)
    asyncio.run(cache.put(_ESTOQUE, TranslateResult(cached_spec, "ollama")))

    async def _never_called(_prompt: str) -> TranslateResult:
        raise AssertionError("tradutor não deve ser chamado em cache hit")

    pipeline = MachinePipeline(
        embedder=OfflineHashEmbedder(),
        store=InMemorySpecStore(),
        cache=cache,
        translator=_never_called,
    )

    res = asyncio.run(pipeline.generate(_ESTOQUE))
    assert res.source == "cache"
    assert res.spec.name == "estoque_simples"
    assert "index.html" in res.files
    apps = asyncio.run(pipeline.list_apps())
    assert len(apps) == 1
    assert apps[0].app_id == res.app_id


def test_translator_optional_litellm_env_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    import types

    spec = fallback_spec_from_prompt(_ENCOMENDA)
    raw = json.dumps(spec.model_dump(mode="json"), ensure_ascii=False)

    fake_litellm = types.SimpleNamespace(
        completion=MagicMock(
            return_value={"choices": [{"message": {"content": raw}}]}
        )
    )
    monkeypatch.setitem(__import__("sys").modules, "litellm", fake_litellm)
    monkeypatch.setenv("YBY_MACHINE_TRANSLATOR", "litellm")

    res = asyncio.run(prompt_to_spec_result("encomendas via litellm"))
    assert res.source == "litellm"
    assert res.spec.name == "encomendas"
    fake_litellm.completion.assert_called_once()

    fake_litellm.completion.side_effect = TimeoutError("timeout simulado")
    res_fb = asyncio.run(prompt_to_spec_result(_OFICINA))
    assert res_fb.source == "fallback"
    assert res_fb.spec.name == "oficina_os"


def test_optional_adapters_fallback_to_memory() -> None:
    from src.yby_machine.cache import (
        AsyncSpecFingerprintCache,
        RedisTranslateCache,
        create_translate_cache_from_env,
    )
    from src.yby_machine.embedder import OfflineHashEmbedder, OllamaEmbedder
    from src.yby_machine.store import InMemorySpecStore, cosine_similarity
    from src.yby_machine.store_pgvector import PgVectorSpecStore, create_spec_store_from_env

    # Sem env -> padrão em memória
    assert isinstance(create_spec_store_from_env({}), InMemorySpecStore)
    assert isinstance(create_translate_cache_from_env({}), AsyncSpecFingerprintCache)

    # PgVector com erro de conexão degrada para memória
    async def _broken_conn():  # noqa: ANN202
        raise ConnectionError("sem postgres")

    pg_store = PgVectorSpecStore(dsn="postgresql://fake", connection_factory=_broken_conn)
    embedder = OfflineHashEmbedder()
    vec = asyncio.run(embedder.embed(_ENCOMENDA))
    saved = asyncio.run(
        pg_store.save(
            prompt=_ENCOMENDA,
            embedding=vec,
            spec=fallback_spec_from_prompt(_ENCOMENDA),
            source="fallback",
        )
    )
    found = asyncio.run(pg_store.find_similar(vec, min_similarity=0.92))
    assert found is not None and found.app_id == saved.app_id
    assert asyncio.run(pg_store.get_app(saved.app_id)) is not None
    assert len(asyncio.run(pg_store.list_apps())) == 1

    # Redis com erro de conexão degrada para memória; com mock async funciona
    class _BrokenRedis:
        async def get(self, _key: str):  # noqa: ANN202
            raise ConnectionError("sem redis")

        async def set(self, _key: str, _val: str, ex: int = 60):  # noqa: ANN202
            raise ConnectionError("sem redis")

    broken_cache = RedisTranslateCache("redis://fake", client=_BrokenRedis())
    tr = TranslateResult(fallback_spec_from_prompt(_ESTOQUE), "fallback")
    asyncio.run(broken_cache.put(_ESTOQUE, tr))
    hit_fb = asyncio.run(broken_cache.get(_ESTOQUE))
    assert hit_fb is not None and hit_fb.spec.name == "estoque_simples"

    class _MockRedis:
        def __init__(self) -> None:
            self.data: dict[str, str] = {}

        async def get(self, key: str) -> str | None:
            return self.data.get(key)

        async def set(self, key: str, val: str, ex: int = 60) -> None:
            assert ex >= 1
            self.data[key] = val

    ok_cache = RedisTranslateCache("redis://fake", client=_MockRedis())
    asyncio.run(ok_cache.put(_OFICINA, TranslateResult(fallback_spec_from_prompt(_OFICINA), "ollama")))
    hit_redis = asyncio.run(ok_cache.get(_OFICINA))
    assert hit_redis is not None and hit_redis.source == "ollama"

    # OllamaEmbedder com erro cai no determinístico offline
    ollama_emb = OllamaEmbedder(base_url="http://127.0.0.1:1", timeout=0.05)
    v_offline = asyncio.run(embedder.embed(_ENCOMENDA))
    v_fallback = asyncio.run(ollama_emb.embed(_ENCOMENDA))
    assert cosine_similarity(v_offline, v_fallback) == pytest.approx(1.0)


def test_http_apps_list_get_reuse_and_lifespan() -> None:
    from src.yby_machine.cache import AsyncSpecFingerprintCache
    from src.yby_machine.embedder import OfflineHashEmbedder
    from src.yby_machine.pipeline import MachinePipeline
    from src.yby_machine.store import InMemorySpecStore

    closed = {"called": False}

    class _TrackedStore(InMemorySpecStore):
        async def close(self) -> None:
            closed["called"] = True

    async def _translator(prompt: str) -> TranslateResult:
        return TranslateResult(fallback_spec_from_prompt(prompt), "ollama")

    pipeline = MachinePipeline(
        embedder=OfflineHashEmbedder(),
        store=_TrackedStore(),
        cache=AsyncSpecFingerprintCache(),
        translator=_translator,
    )

    with TestClient(create_app(pipeline=pipeline)) as client:
        r1 = client.post("/api/machine/generate", json={"prompt": _ENCOMENDA})
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1["source"] == "ollama"
        app_id = body1["app_id"]
        assert app_id

        # Segundo pedido igual aciona reuso (>= 0.92)
        r2 = client.post("/api/machine/generate", json={"prompt": _ENCOMENDA})
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["source"] == "reuse"
        assert body2["app_id"] == app_id

        # GET /api/machine/apps
        listed = client.get("/api/machine/apps")
        assert listed.status_code == 200
        items = listed.json()
        assert len(items) == 1
        assert items[0]["app_id"] == app_id
        assert items[0]["name"] == "encomendas"
        assert items[0]["title"]
        assert "description" in items[0]
        assert items[0]["created_at"]

        # GET /api/machine/apps/{app_id}
        detail = client.get(f"/api/machine/apps/{app_id}")
        assert detail.status_code == 200
        d = detail.json()
        assert d["app_id"] == app_id
        assert d["spec"]["name"] == "encomendas"
        assert "index.html" in d["files"]
        assert "app.js" in d["files"]
        assert "indexedDB" in d["files"]["app.js"]

        # 404 para app inexistente
        missing = client.get("/api/machine/apps/nao_existe")
        assert missing.status_code == 404

    assert closed["called"] is True

