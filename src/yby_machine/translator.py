"""Prompt → YBYSpec via Ollama local (format json). Sem nuvem automática (D12)."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from src.engine.config import DEFAULT_LOCAL_MODEL, DEFAULT_OLLAMA_BASE_URL, EngineConfig
from src.engine.providers import OllamaProvider, ProviderError
from src.yby_machine.cache import SpecFingerprintCache
from src.yby_machine.fallback import fallback_spec_from_prompt
from src.yby_machine.spec import YBYSpec, yby_spec_schema_for_prompt

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

SourceKind = Literal["ollama", "fallback"]


def _system_prompt() -> str:
    schema = yby_spec_schema_for_prompt()
    return (
        "Você é o tradutor Spec-First do YBY Machine. "
        "Responda SOMENTE com um objeto JSON válido no schema YBYSpec. "
        "Campos de tipo BR: texto, numero, data, cpf, cnpj, cep, moeda_brl, telefone_br. "
        "payment_statuses: Pago, Pendente/Fiado, Sinal 50%. "
        "pix.payload é string BR Code estática (prefixo 000201). "
        "whatsapp.phone_e164 opcional (dígitos); links usam wa.me. "
        "Sem HTML. Sem markdown. Só JSON.\n"
        f"JSON Schema YBYSpec: {schema}"
    )


@dataclass(frozen=True)
class TranslateResult:
    spec: YBYSpec
    source: SourceKind


async def prompt_to_spec(
    prompt: str,
    *,
    provider: OllamaProvider | None = None,
    model: str | None = None,
    use_fallback_on_error: bool = True,
    cache: SpecFingerprintCache | None = None,
) -> YBYSpec:
    """Traduz prompt em YBYSpec. Falha → fallback seguro (sem nuvem)."""

    result = await prompt_to_spec_result(
        prompt,
        provider=provider,
        model=model,
        use_fallback_on_error=use_fallback_on_error,
        cache=cache,
    )
    return result.spec


async def prompt_to_spec_result(
    prompt: str,
    *,
    provider: OllamaProvider | None = None,
    model: str | None = None,
    use_fallback_on_error: bool = True,
    cache: SpecFingerprintCache | None = None,
) -> TranslateResult:
    """Igual a `prompt_to_spec`, com indicação explícita da origem."""

    text = (prompt or "").strip()
    if not text:
        if use_fallback_on_error:
            return TranslateResult(fallback_spec_from_prompt(""), "fallback")
        raise ValueError("prompt vazio")

    if cache is not None:
        hit = cache.get(text)
        if hit is not None:
            return hit

    owns_provider = provider is None
    if provider is None:
        try:
            cfg = EngineConfig.from_env()
            base = cfg.ollama_base_url
            model = model or cfg.local_model
            timeout = cfg.ollama_timeout
        except Exception:
            base = DEFAULT_OLLAMA_BASE_URL
            model = model or DEFAULT_LOCAL_MODEL
            timeout = 60.0
        provider = OllamaProvider(base, timeout=timeout)

    model = model or DEFAULT_LOCAL_MODEL
    result: TranslateResult | None = None

    try:
        try:
            raw = await asyncio.to_thread(
                provider.complete,
                text,
                model=model,
                system=_system_prompt(),
                ollama_format="json",
            )
            result = TranslateResult(parse_spec_json(raw), "ollama")
        except (ProviderError, ValidationError, ValueError, json.JSONDecodeError, OSError):
            if use_fallback_on_error:
                result = TranslateResult(fallback_spec_from_prompt(text), "fallback")
            else:
                raise
    finally:
        if owns_provider:
            provider.close()

    assert result is not None
    if cache is not None:
        cache.put(text, result)
    return result


def parse_spec_json(raw: str) -> YBYSpec:
    """Extrai e valida YBYSpec a partir do texto do modelo."""

    payload = _extract_json_object(raw)
    return YBYSpec.model_validate(_normalize_payload(payload))


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("resposta vazia do tradutor")
    match = _JSON_FENCE.search(text)
    if match:
        text = match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("nenhum objeto JSON na resposta")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("JSON do tradutor deve ser um objeto")
    return data


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Ajustes leves para JSON incompleto do modelo pequeno."""

    out = dict(payload)
    if "name" not in out and "title" in out:
        raw_name = str(out["title"]).casefold().replace(" ", "_")
        # Mantém só identificador válido para passar no Field validator
        cleaned = re.sub(r"[^a-z0-9_]", "", raw_name.replace("-", "_"))
        out["name"] = (cleaned or "app")[:80]
    if "title" not in out and "name" in out:
        out["title"] = str(out["name"])
    entities = out.get("entities")
    if not isinstance(entities, list) or not entities:
        raise ValueError("entities ausente ou vazia")
    return out
