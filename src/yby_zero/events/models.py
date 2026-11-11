from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class YBYEvent(BaseModel):
    schema_version: str = "0.1"
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str
    target: str | None = None
    event_type: str
    priority: str = "normal"
    privacy_level: str = "P1"
    payload: dict[str, Any] = Field(default_factory=dict)
