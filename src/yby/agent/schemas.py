"""Schemas JSON do agente YBY."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


class AgentToolStep(BaseModel):
    action: Literal["tool"] = "tool"
    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    justification: str = Field(default="", max_length=500)


class AgentSourceCitation(BaseModel):
    source: str = Field(min_length=1)
    excerpt: str = ""
    score: float | None = None


class AgentFinishAnswer(BaseModel):
    text: str = Field(min_length=1)
    sources: list[AgentSourceCitation] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
    needs_approval: bool = False
    warnings: list[str] = Field(default_factory=list, max_length=20)


class AgentFinishStep(BaseModel):
    action: Literal["finish"] = "finish"
    answer: AgentFinishAnswer | dict[str, Any] = Field(default_factory=dict)

    @field_validator("answer", mode="before")
    @classmethod
    def _coerce_answer(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return AgentFinishAnswer.model_validate(value)
        return value


class AgentStructuredResponse(BaseModel):
    """Resposta final estruturada exposta ao chamador."""

    answer: str = ""
    sources: list[dict[str, Any]] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
    needs_approval: bool = False
    warnings: list[str] = Field(default_factory=list)
    trace_id: str
    latency_ms: float = Field(ge=0)
    token_usage: dict[str, Any] | None = None
    status: str = "error"


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