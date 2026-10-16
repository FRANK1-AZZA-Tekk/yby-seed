"""Contratos de auditoria sem conteúdo de conversa."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


AuditStatus = Literal[
    "ok",
    "unavailable",
    "model_missing",
    "empty",
    "client_error",
    "interrupted",
]

EXIT_BY_STATUS = {
    "ok": 0,
    "unavailable": 2,
    "model_missing": 3,
    "empty": 4,
    "client_error": 7,
    "interrupted": 130,
}


class AuditStart(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    started_at_ms: int = Field(strict=True, ge=0)
    backend: Literal["ollama"] = "ollama"
    model: str = Field(min_length=1, max_length=128)


class AuditFinish(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    finished_at_ms: int = Field(strict=True, ge=0)
    elapsed_ms: int = Field(strict=True, ge=0)
    status: AuditStatus
    exit_code: int = Field(strict=True)

    @model_validator(mode="after")
    def validate_exit_code(self) -> "AuditFinish":
        if self.exit_code != EXIT_BY_STATUS[self.status]:
            raise ValueError("Status e código de saída incompatíveis.")
        return self
