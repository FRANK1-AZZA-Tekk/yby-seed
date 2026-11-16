"""Relatório de dry-run do adaptador Cursor fake (sem MCP)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

REPORT_SCHEMA = "yby-cursor-fake/v1"
StepAction = Literal["skip_no_mcp"]


class SimulatedStep(BaseModel):
    """Etapa pretendida; nunca executada neste adaptador."""

    id: str
    order: int
    kind: str
    objective: str
    files: list[str] = Field(default_factory=list)
    allowed_commands: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    action: StepAction = "skip_no_mcp"
    executed: bool = False


class DryRunReport(BaseModel):
    """Saída do simulate: metadados do plano + steps sem efeito colateral."""

    schema_version: Literal["yby-cursor-fake/v1"] = REPORT_SCHEMA
    plan_id: str
    plan_version: int
    brief_id: str
    plan_status: str
    adapter: Literal["cursor_fake"] = "cursor_fake"
    warning: str = (
        "adaptador fake / sem MCP: nenhum arquivo escrito, nenhum comando executado"
    )
    steps: list[SimulatedStep] = Field(default_factory=list)
    cited_files: list[str] = Field(default_factory=list)
