"""Local telemetry gateway prototype.

This endpoint validates and queues telemetry only. Durable persistence,
MQTT ingestion and authenticated access are not implemented; do not use it as a
production API. Bind to loopback or a trusted network only.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

QUEUE_MAXSIZE = 1000
telemetry_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)


class Telemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    metrics: dict[str, float | int | bool] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


app = FastAPI(title="YBY SEED Gateway (prototype)", version="0.2.1")


@app.post("/telemetry", status_code=202)
async def receive_telemetry(data: Telemetry) -> dict[str, Any]:
    payload = data.model_dump(mode="json")
    try:
        telemetry_queue.put_nowait(payload)
    except asyncio.QueueFull as exc:
        raise HTTPException(status_code=503, detail="Telemetry queue is full") from exc
    return {
        "status": "queued_in_memory",
        "persistence": "not_implemented",
        "queue_size": telemetry_queue.qsize(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "prototype",
        "persistence": "not_implemented",
        "queue_size": telemetry_queue.qsize(),
    }
