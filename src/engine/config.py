"""Configuração do motor. Segredos só vêm de variáveis de ambiente."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv

from src.engine.routing import DEFAULT_HEAVY_PHRASES

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_LOCAL_MODEL = "qwen2.5-coder:3b"
DEFAULT_CLOUD_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_CLOUD_MODEL = "openrouter/free"
DEFAULT_CLOUD_FALLBACK_BASE_URL = "https://api.x.ai/v1"
DEFAULT_CLOUD_FALLBACK_MODEL = "grok-4.7"
DEFAULT_HEAVY_MIN_CHARS = 1200
DEFAULT_HEAVY_MIN_LINES = 25
DEFAULT_HEAVY_MIN_QUESTIONS = 3
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_CACHE_TTL_SECONDS = 3600.0
DEFAULT_CLOUD_MAX_CHARS = 12000


class EngineConfigError(ValueError):
    """Variável de ambiente do motor inválida."""


@dataclass(frozen=True)
class EngineConfig:
    """Limiares e destinos do motor. A chave de nuvem pode ser vazia."""

    ollama_base_url: str
    local_model: str
    cloud_base_url: str
    cloud_model: str
    cloud_api_key: str
    cloud_fallback_base_url: str
    cloud_fallback_model: str
    cloud_fallback_api_key: str
    heavy_min_chars: int
    heavy_min_lines: int
    heavy_min_questions: int
    heavy_phrases: tuple[str, ...]
    ollama_timeout: float
    cloud_timeout: float
    cache_ttl_seconds: float
    cloud_max_chars: int

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> EngineConfig:
        """Lê a configuração. Sem `environ`, carrega `.env` sem sobrescrever o processo."""

        if environ is None:
            load_dotenv(override=False)
            source: Mapping[str, str] = os.environ
        else:
            source = environ

        cloud_api_key = _first(source, "YBY_CLOUD_API_KEY", "OPENROUTER_API_KEY")
        fallback_key = _first(
            source, "YBY_GROK_API_KEY", "YBY_CLOUD_FALLBACK_API_KEY", "XAI_API_KEY"
        )
        fallback_base = _first(source, "YBY_GROK_BASE_URL", "YBY_CLOUD_FALLBACK_BASE_URL")
        fallback_model = _first(source, "YBY_GROK_MODEL", "YBY_CLOUD_FALLBACK_MODEL")
        max_chars_raw = _first(source, "YBY_CLOUD_CONTEXT_MAX_CHARS", "YBY_CLOUD_MAX_CHARS")

        return cls(
            ollama_base_url=_text(source, "YBY_OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL,
            local_model=_text(source, "YBY_LOCAL_MODEL") or DEFAULT_LOCAL_MODEL,
            cloud_base_url=_text(source, "YBY_CLOUD_BASE_URL") or DEFAULT_CLOUD_BASE_URL,
            cloud_model=_text(source, "YBY_CLOUD_MODEL") or DEFAULT_CLOUD_MODEL,
            cloud_api_key=cloud_api_key,
            cloud_fallback_base_url=fallback_base or DEFAULT_CLOUD_FALLBACK_BASE_URL,
            cloud_fallback_model=fallback_model or DEFAULT_CLOUD_FALLBACK_MODEL,
            cloud_fallback_api_key=fallback_key,
            heavy_min_chars=_positive_int(source, "YBY_HEAVY_MIN_CHARS", DEFAULT_HEAVY_MIN_CHARS),
            heavy_min_lines=_positive_int(source, "YBY_HEAVY_MIN_LINES", DEFAULT_HEAVY_MIN_LINES),
            heavy_min_questions=_positive_int(
                source, "YBY_HEAVY_MIN_QUESTIONS", DEFAULT_HEAVY_MIN_QUESTIONS
            ),
            heavy_phrases=_phrases(source.get("YBY_HEAVY_PHRASES")),
            ollama_timeout=_positive_float(source, "YBY_OLLAMA_TIMEOUT", DEFAULT_TIMEOUT_SECONDS),
            cloud_timeout=_positive_float(source, "YBY_CLOUD_TIMEOUT", DEFAULT_TIMEOUT_SECONDS),
            cache_ttl_seconds=_non_negative_float(
                source, "YBY_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS
            ),
            cloud_max_chars=_parse_non_negative_int(
                max_chars_raw, "YBY_CLOUD_CONTEXT_MAX_CHARS", DEFAULT_CLOUD_MAX_CHARS
            ),
        )


def _text(source: Mapping[str, str], name: str) -> str:
    return source.get(name, "").strip()


def _first(source: Mapping[str, str], *names: str) -> str:
    for name in names:
        value = _text(source, name)
        if value:
            return value
    return ""


def _positive_int(source: Mapping[str, str], name: str, default: int) -> int:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise EngineConfigError(f"{name} deve ser um inteiro, recebi {raw!r}.") from exc
    if value < 1:
        raise EngineConfigError(f"{name} deve ser maior ou igual a 1.")
    return value


def _parse_non_negative_int(raw: str, name: str, default: int) -> int:
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise EngineConfigError(f"{name} deve ser um inteiro, recebi {raw!r}.") from exc
    if value < 0:
        raise EngineConfigError(f"{name} deve ser maior ou igual a 0.")
    return value


def _positive_float(source: Mapping[str, str], name: str, default: float) -> float:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise EngineConfigError(f"{name} deve ser um número, recebi {raw!r}.") from exc
    if value <= 0:
        raise EngineConfigError(f"{name} deve ser maior que 0.")
    return value


def _non_negative_float(source: Mapping[str, str], name: str, default: float) -> float:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise EngineConfigError(f"{name} deve ser um número, recebi {raw!r}.") from exc
    if value < 0:
        raise EngineConfigError(f"{name} deve ser maior ou igual a 0.")
    return value


def _phrases(raw: str | None) -> tuple[str, ...]:
    if raw is None or not raw.strip():
        return DEFAULT_HEAVY_PHRASES
    phrases = tuple(part.strip().casefold() for part in raw.split(",") if part.strip())
    return phrases or DEFAULT_HEAVY_PHRASES
