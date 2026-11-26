"""Schemas Pydantic v2 do Módulo D (sincronização idempotente Xiaomi 12 -> PC Hub)."""

from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EMBEDDING_DIM = 384


class EdgeEvent(BaseModel):
    """Evento capturado offline no Xiaomi 12 (Termux/Mosquitto local) com chave idempotente."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., min_length=1, max_length=128)
    device_id: str = Field(..., min_length=1, max_length=64)
    source_node: str = Field(default="xiaomi12", min_length=1, max_length=64)
    topic: str = Field(..., min_length=1, max_length=256)
    payload: dict[str, Any] = Field(default_factory=dict)
    text_summary: str = Field(default="", max_length=4000)
    captured_at: float = Field(default_factory=time.time)
    sensitivity: Literal["private", "public"] = "private"
    embedding: list[float] | None = None
    sync_origin: str | None = None


class EdgeSyncBatchRequest(BaseModel):
    """Lote enviado pelo Xiaomi 12 ao reconectar no túnel Tailscale."""

    model_config = ConfigDict(extra="forbid")

    source_node: str = Field(default="xiaomi12", min_length=1, max_length=64)
    events: list[EdgeEvent] = Field(..., min_length=1, max_length=256)


class EdgeSyncBatchResponse(BaseModel):
    """Resposta do endpoint `/edge/sync` com contadores idempotentes."""

    model_config = ConfigDict(extra="forbid")

    accepted: int
    duplicates: int
    failed: int
    last_cursor: str | None = None
    store_backend: str


class EdgeSyncStatus(BaseModel):
    """Resumo operacional da ponte de sincronização."""

    model_config = ConfigDict(extra="forbid")

    store_backend: str
    total_stored: int
    pending_fallback: int
    healthy: bool


class StoredEdgeEvent(BaseModel):
    """Registro recuperado do banco vetorial ou fallback SQLite."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    device_id: str
    source_node: str
    topic: str
    payload: dict[str, Any]
    captured_at: float
    sensitivity: Literal["private", "public"]
    score: float | None = None
