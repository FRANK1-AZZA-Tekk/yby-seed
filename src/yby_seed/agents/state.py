from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from src.yby_seed.models import DomainKind, StructuredCode


class MissionStatus(StrEnum):
    PENDING = "pending"
    ARCHITECTING = "architecting"
    BUILDING = "building"
    VALIDATING = "validating"
    AUDITING = "auditing"
    SUCCESS = "success"
    FAILED = "failed"


class MissionState(BaseModel):
    mission_id: str
    user_intent: str
    domain: DomainKind
    rag_context: str = ""
    architecture_plan: dict[str, Any] | None = None
    gpio_manifest: dict[str, Any] | None = None
    generated_code: StructuredCode | None = None
    validation_logs: list[str] = Field(default_factory=list)
    attempt_count: int = 0
    status: MissionStatus = MissionStatus.PENDING
    last_stdout: str = ""
    last_stderr: str = ""
    auditor_guidance: str = ""
