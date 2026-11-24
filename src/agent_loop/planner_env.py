"""Variáveis de ambiente específicas do planner Ollama (experimental)."""

from __future__ import annotations

import os
from collections.abc import Mapping

from src.engine.config import EngineConfigError

_PLANNER_FORMAT_ENV = "YBY_PLANNER_OLLAMA_FORMAT"
_PLANNER_PROMPT_MAX_CHARS_ENV = "YBY_PLANNER_PROMPT_MAX_CHARS"
DEFAULT_PLANNER_PROMPT_MAX_CHARS = 8192
MIN_PLANNER_PROMPT_MAX_CHARS = 256


def planner_ollama_format_from_env(
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """`json` habilita `format` no POST; vazio desliga; outro valor falha antes de HTTP."""

    source = environ if environ is not None else os.environ
    raw = source.get(_PLANNER_FORMAT_ENV, "").strip()
    if not raw:
        return None
    if raw.casefold() != "json":
        raise EngineConfigError(
            f"{_PLANNER_FORMAT_ENV} só aceita 'json' (experimental); recebi {raw!r}."
        )
    return "json"


def planner_prompt_max_chars_from_env(
    environ: Mapping[str, str] | None = None,
) -> int:
    """Teto conservador (caracteres Python) para system + prompt do planner."""

    source = environ if environ is not None else os.environ
    raw = source.get(_PLANNER_PROMPT_MAX_CHARS_ENV, "").strip()
    if not raw:
        return DEFAULT_PLANNER_PROMPT_MAX_CHARS
    try:
        value = int(raw)
    except ValueError as exc:
        raise EngineConfigError(
            f"{_PLANNER_PROMPT_MAX_CHARS_ENV} deve ser um inteiro; recebi {raw!r}."
        ) from exc
    if value < MIN_PLANNER_PROMPT_MAX_CHARS:
        raise EngineConfigError(
            f"{_PLANNER_PROMPT_MAX_CHARS_ENV} deve ser >= {MIN_PLANNER_PROMPT_MAX_CHARS}; "
            f"recebi {value}."
        )
    return value