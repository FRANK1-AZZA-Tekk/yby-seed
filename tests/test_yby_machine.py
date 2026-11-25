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
