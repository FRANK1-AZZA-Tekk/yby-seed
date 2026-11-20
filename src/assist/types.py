"""Tipos compartilhados do assist."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

PolicyAction = Literal["allow", "confirm", "refuse"]


@dataclass(frozen=True)
class ToolProposal:
    """Proposta estruturada (alias ou Ollama) — ainda não é resultado."""

    tool: str
    args: dict[str, Any]
    source: Literal["alias", "ollama", "session"] = "ollama"


@dataclass(frozen=True)
class PolicyDecision:
    action: PolicyAction
    reason: str


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    tool: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    narration: str = ""


@dataclass(frozen=True)
class TurnOutcome:
    """Resposta de um turno, com camadas separadas."""

    proposal: ToolProposal | None
    policy: PolicyDecision | None
    result: ToolResult | None
    user_message: str
