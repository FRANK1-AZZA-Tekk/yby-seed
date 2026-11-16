"""Schemas JSON do agente YBY."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


class AgentToolStep(BaseModel):
    action: Literal["tool"] = "tool"
    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    justification: str = Field(default="", max_length=500)


class AgentFinishStep(BaseModel):
    action: Literal["finish"] = "finish"
    answer: dict[str, Any] = Field(default_factory=dict)


class AgentAbortStep(BaseModel):
    action: Literal["abort"] = "abort"
    reason: str = Field(min_length=1, max_length=500)


AgentStep = AgentToolStep | AgentFinishStep | AgentAbortStep


def parse_agent_step(raw: str) -> AgentStep:
    text = raw.strip()
    if not text:
        raise ValueError("resposta vazia do modelo")
    match = _JSON_FENCE.search(text)
    if match:
        text = match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("nenhum objeto JSON na resposta")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("JSON deve ser um objeto")
    action = payload.get("action")
    if action == "tool":
        return AgentToolStep.model_validate(payload)
    if action == "finish":
        return AgentFinishStep.model_validate(payload)
    if action == "abort":
        return AgentAbortStep.model_validate(payload)
    raise ValueError(f"ação desconhecida: {action!r}")


def format_validation_error(exc: ValidationError) -> str:
    return "; ".join(f"{err['loc']}: {err['msg']}" for err in exc.errors())