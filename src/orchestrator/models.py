"""Seleção de modelo local-first (origem: yby-core/router.py + benchmarks)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .classify import TaskType

# Benchmark yby-seed-local: qwen2.5-coder:3b liderou em velocidade na GTX 1650.
DEFAULT_LOCAL_MODEL = "qwen2.5-coder:3b"
DEFAULT_CLOUD_MODEL = "openai/gpt-4o-mini"


@dataclass(frozen=True)
class ModelChoice:
    provider: str
    model: str
    allow_cloud: bool
    reason: str


def choose_model(
    task_type: TaskType,
    *,
    sensitive: bool = False,
    privacy_level: str = "P1",
) -> ModelChoice:
    local_model = os.getenv("YBY_LOCAL_MODEL", DEFAULT_LOCAL_MODEL)
    cloud_model = os.getenv("YBY_CLOUD_MODEL", DEFAULT_CLOUD_MODEL)

    if sensitive or privacy_level in {"P2", "P3"}:
        return ModelChoice(
            provider="ollama",
            model=local_model,
            allow_cloud=False,
            reason="Dados sensíveis ou P2/P3 ficam no Ollama local",
        )

    if task_type in {"chat", "firmware", "memory", "hardware"}:
        return ModelChoice(
            provider="ollama",
            model=local_model,
            allow_cloud=False,
            reason=f"Tarefa {task_type} prioriza modelo local",
        )

    return ModelChoice(
        provider="openrouter",
        model=cloud_model,
        allow_cloud=True,
        reason="Pesquisa pode usar fallback em nuvem sanitizado",
    )
