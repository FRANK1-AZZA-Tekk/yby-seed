"""Prompt -> YBYSpec via Ollama local (format json). LiteLLM só com env explícita (D12)."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from src.engine.config import DEFAULT_LOCAL_MODEL, DEFAULT_OLLAMA_BASE_URL, EngineConfig
from src.engine.providers import OllamaProvider, ProviderError
from src.yby_machine.cache import SpecFingerprintCache
from src.yby_machine.fallback import fallback_spec_from_prompt
from src.yby_machine.ports import TranslateCachePort
from src.yby_machine.spec import YBYSpec, yby_spec_schema_for_prompt

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

SourceKind = Literal["ollama", "litellm", "fallback"]
CacheLike = SpecFingerprintCache | TranslateCachePort


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


async def _cache_get(cache: CacheLike, prompt: str) -> TranslateResult | None:
    res = cache.get(prompt)
    if inspect.isawaitable(res):
        return await res
    return res


async def _cache_put(cache: CacheLike, prompt: str, result: TranslateResult) -> None:
    res = cache.put(prompt, result)
    if inspect.isawaitable(res):
        await res


def _litellm_complete_sync(
    prompt: str,
    *,
    model: str,
    system: str,
    timeout: float,
) -> str:
    import litellm

    resp = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        timeout=timeout,
    )
    choices = getattr(resp, "choices", None)
    if not choices and isinstance(resp, dict):
        choices = resp.get("choices")
    if not choices:
        raise ValueError("resposta vazia do LiteLLM")
    first = choices[0]
    message = getattr(first, "message", None) if not isinstance(first, dict) else first.get("message")
    content = (
        getattr(message, "content", None)
        if not isinstance(message, dict)
        else message.get("content")
    )
    if not content:
        raise ValueError("conteúdo vazio do LiteLLM")
    return str(content)


async def prompt_to_spec(
    prompt: str,
    *,
    provider: OllamaProvider | None = None,
    model: str | None = None,
    use_fallback_on_error: bool = True,
    cache: CacheLike | None = None,
    timeout: float | None = None,
    backend: str | None = None,
) -> YBYSpec:
    """Traduz prompt em YBYSpec. Falha -> fallback seguro (sem nuvem automática)."""

    result = await prompt_to_spec_result(
        prompt,
        provider=provider,
        model=model,
        use_fallback_on_error=use_fallback_on_error,
        cache=cache,
        timeout=timeout,
        backend=backend,
    )
    return result.spec


async def prompt_to_spec_result(
    prompt: str,
    *,
    provider: OllamaProvider | None = None,
    model: str | None = None,
    use_fallback_on_error: bool = True,
    cache: CacheLike | None = None,
    timeout: float | None = None,
    backend: str | None = None,
) -> TranslateResult:
    """Igual a `prompt_to_spec`, com indicação explícita da origem."""

    text = (prompt or "").strip()
    if not text:
        if use_fallback_on_error:
            return TranslateResult(fallback_spec_from_prompt(""), "fallback")
        raise ValueError("prompt vazio")

    if cache is not None:
        hit = await _cache_get(cache, text)
        if hit is not None:
            return hit

    selected_backend = (
        (backend if backend is not None else os.environ.get("YBY_MACHINE_TRANSLATOR", "ollama"))
        .strip()
        .casefold()
    )

    # Ramo LiteLLM SOMENTE quando explicitamente pedido via env/parâmetro e sem provider Ollama injetado
    if selected_backend == "litellm" and provider is None:
        litellm_model = (
            model
            or os.environ.get("YBY_MACHINE_LITELLM_MODEL", "").strip()
            or f"ollama/{DEFAULT_LOCAL_MODEL}"
        )
        eff_timeout = float(timeout if timeout is not None else 60.0)
        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(
                    _litellm_complete_sync,
                    text,
                    model=litellm_model,
                    system=_system_prompt(),
                    timeout=eff_timeout,
                ),
                timeout=eff_timeout,
            )
            result = TranslateResult(parse_spec_json(raw), "litellm")
        except Exception:  # noqa: BLE001
            if use_fallback_on_error:
                result = TranslateResult(fallback_spec_from_prompt(text), "fallback")
            else:
                raise
        if cache is not None:
            await _cache_put(cache, text, result)
        return result

    owns_provider = provider is None
    eff_timeout = float(timeout) if timeout is not None else 60.0
    if provider is None:
        try:
            cfg = EngineConfig.from_env()
            base = cfg.ollama_base_url
            model = model or cfg.local_model
            if timeout is None:
                eff_timeout = cfg.ollama_timeout
        except Exception:  # noqa: BLE001
            base = DEFAULT_OLLAMA_BASE_URL
            model = model or DEFAULT_LOCAL_MODEL
        provider = OllamaProvider(base, timeout=eff_timeout)

    model = model or DEFAULT_LOCAL_MODEL
    result: TranslateResult | None = None

    try:
        try:
            coro = asyncio.to_thread(
                provider.complete,
                text,
                model=model,
                system=_system_prompt(),
                ollama_format="json",
            )
            raw = await asyncio.wait_for(coro, timeout=eff_timeout)
            result = TranslateResult(parse_spec_json(raw), "ollama")
        except (
            ProviderError,
            ValidationError,
            ValueError,
            json.JSONDecodeError,
            OSError,
            TimeoutError,
            asyncio.TimeoutError,
        ):
            if use_fallback_on_error:
                result = TranslateResult(fallback_spec_from_prompt(text), "fallback")
            else:
                raise
    finally:
        if owns_provider:
            provider.close()

    assert result is not None
    if cache is not None:
        await _cache_put(cache, text, result)
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


def _sanitize_ident(raw: Any, *, default: str = "app") -> str:
    text = unicodedata.normalize("NFKD", str(raw or ""))
    ascii_text = "".join(ch for ch in text if not unicodedata.combining(ch))
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", ascii_text.strip().casefold())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = default
    if cleaned[0].isdigit():
        cleaned = f"{default}_{cleaned}"
    return cleaned[:80]


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Ajustes leves para JSON incompleto do modelo pequeno."""

    out = dict(payload)
    if "name" not in out and "title" in out:
        out["name"] = _sanitize_ident(out["title"], default="app")
    elif isinstance(out.get("name"), str) and out["name"].strip():
        out["name"] = _sanitize_ident(out["name"], default="app")
    if "title" not in out and "name" in out:
        out["title"] = str(out["name"])
    entities = out.get("entities")
    if not isinstance(entities, list) or not entities:
        raise ValueError("entities ausente ou vazia")
    normalized_entities: list[Any] = []
    for entity in entities:
        if not isinstance(entity, dict):
            normalized_entities.append(entity)
            continue
        ent = dict(entity)
        if "name" in ent:
            ent["name"] = _sanitize_ident(ent["name"], default="item")
        elif "label" in ent:
            ent["name"] = _sanitize_ident(ent["label"], default="item")
        fields = ent.get("fields")
        if isinstance(fields, list):
            norm_fields: list[Any] = []
            for field in fields:
                if isinstance(field, dict):
                    fld = dict(field)
                    if "name" in fld:
                        fld["name"] = _sanitize_ident(fld["name"], default="campo")
                    elif "label" in fld:
                        fld["name"] = _sanitize_ident(fld["label"], default="campo")
                    norm_fields.append(fld)
                else:
                    norm_fields.append(field)
            ent["fields"] = norm_fields
        normalized_entities.append(ent)
    out["entities"] = normalized_entities
    if isinstance(out.get("actions"), list):
        norm_actions: list[Any] = []
        for action in out["actions"]:
            if isinstance(action, dict):
                act = dict(action)
                if "name" in act:
                    act["name"] = _sanitize_ident(act["name"], default="acao")
                elif "label" in act:
                    act["name"] = _sanitize_ident(act["label"], default="acao")
                norm_actions.append(act)
            else:
                norm_actions.append(action)
        out["actions"] = norm_actions
    return out
