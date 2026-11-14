"""Schemas Pydantic para passos do planner e argumentos de tools."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


class EchoArgs(BaseModel):
    """Saída estruturada de teste — não toca rede nem disco."""

    message: str = Field(min_length=1, max_length=2000)


class VaultSearchArgs(BaseModel):
    """Busca somente leitura no vault."""

    query: str = Field(min_length=1, max_length=500)
    k: int = Field(default=3, ge=1, le=10)


class ToolCallStep(BaseModel):
    action: Literal["tool"] = "tool"
    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class FinishStep(BaseModel):
    action: Literal["finish"] = "finish"
    answer: dict[str, Any] = Field(default_factory=dict)


class AbortStep(BaseModel):
    action: Literal["abort"] = "abort"
    reason: str = Field(min_length=1, max_length=500)


PlannerStep = ToolCallStep | FinishStep | AbortStep


def parse_planner_step(raw: str) -> PlannerStep:
    """Extrai um único objeto JSON do texto do modelo."""

    text = raw.strip()
    if not text:
        raise ValueError("resposta vazia do planner")
    match = _JSON_FENCE.search(text)
    if match:
        text = match.group(1).strip()
    # Primeiro objeto JSON na linha
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("nenhum objeto JSON na resposta")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("JSON do planner deve ser um objeto")
    action = payload.get("action")
    if action == "tool":
        return ToolCallStep.model_validate(payload)
    if action == "finish":
        return FinishStep.model_validate(payload)
    if action == "abort":
        return AbortStep.model_validate(payload)
    raise ValueError(f"ação desconhecida: {action!r}")


def format_validation_error(exc: ValidationError) -> str:
    return "; ".join(f"{err['loc']}: {err['msg']}" for err in exc.errors())