"""Contrato YBY-PLAN (v1). Plano ≠ execução."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


PLAN_SCHEMA = "yby-plan/v1"

StepKind = Literal["read", "analyze", "create", "test", "deliver"]


class PlanStep(BaseModel):
    """Uma etapa ordenada; cada uma exige autorização própria para rodar."""

    id: str = Field(min_length=1, max_length=32)
    order: int = Field(ge=1)
    kind: StepKind
    objective: str = Field(min_length=1, max_length=500)
    files: list[str] = Field(default_factory=list)
    allowed_commands: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    acceptance: str = Field(min_length=1, max_length=500)
    revert: str = Field(min_length=1, max_length=500)
    depends_on: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    authorized: bool = False


class YbyPlan(BaseModel):
    """Plano versionado ligado a um brief. Não autoriza subprocessos."""

    schema_version: Literal["yby-plan/v1"] = PLAN_SCHEMA
    id: str = Field(min_length=1, max_length=64)
    brief_id: str = Field(min_length=1, max_length=64)
    version: int = Field(default=1, ge=1)
    status: Literal["draft", "validated", "rejected"] = "draft"
    steps: list[PlanStep] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: _now())
    updated_at: str = Field(default_factory=lambda: _now())

    def touch(self) -> None:
        self.updated_at = _now()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
