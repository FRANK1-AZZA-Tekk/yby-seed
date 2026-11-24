"""Variáveis de ambiente específicas do planner Ollama (experimental)."""

from __future__ import annotations

import os
from collections.abc import Mapping

from src.engine.config import EngineConfigError

_PLANNER_FORMAT_ENV = "YBY_PLANNER_OLLAMA_FORMAT"


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