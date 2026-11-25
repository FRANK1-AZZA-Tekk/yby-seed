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
from src.yby_machine.fallback import fallback_spec_from_prompt
from src.yby_machine.spec import YBYSpec

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

SourceKind = Literal["ollama", "fallback"]

_SYSTEM = (
    "Você é o tradutor Spec-First do YBY Machine. "
    "Responda SOMENTE com um objeto JSON válido no schema YBYSpec. "
    "Campos de tipo BR: texto, numero, data, cpf, cnpj, cep, moeda_brl, telefone_br. "
    "payment_statuses: Pago, Pendente/Fiado, Sinal 50%. "
    "pix.payload é string BR Code estática (MVP). "
    "whatsapp usa wa.me. Sem HTML. Sem markdown. Só JSON."
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
) -> YBYSpec:
    """Traduz prompt em YBYSpec. Falha → fallback seguro (sem nuvem)."""

    result = await prompt_to_spec_result(
        prompt,
        provider=provider,
        model=model,
        use_fallback_on_error=use_fallback_on_error,
    )
    return result.spec


async def prompt_to_spec_result(
    prompt: str,
    *,
    provider: OllamaProvider | None = None,
    model: str | None = None,
    use_fallback_on_error: bool = True,
) -> TranslateResult:
    """Igual a `prompt_to_spec`, com indicação explícita da origem."""

    text = (prompt or "").strip()
    if not text:
        if use_fallback_on_error:
            return TranslateResult(fallback_spec_from_prompt(""), "fallback")
        raise ValueError("prompt vazio")

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

    try:
        raw = await asyncio.to_thread(
            provider.complete,
            text,
            model=model,
            system=_SYSTEM,
            ollama_format="json",
        )
        return TranslateResult(parse_spec_json(raw), "ollama")
    except (ProviderError, ValidationError, ValueError, json.JSONDecodeError, OSError):
        if use_fallback_on_error:
            return TranslateResult(fallback_spec_from_prompt(text), "fallback")
        raise
    finally:
        if owns_provider:
            provider.close()


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
        out["name"] = str(out["title"]).casefold().replace(" ", "_")[:80]
    if "title" not in out and "name" in out:
        out["title"] = str(out["name"])
    entities = out.get("entities")
    if not isinstance(entities, list) or not entities:
        raise ValueError("entities ausente ou vazia")
    return out
