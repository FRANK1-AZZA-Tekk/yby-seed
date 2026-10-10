"""Local telemetry gateway prototype.

This module is not an authenticated public API and must remain bound to a
trusted local network. Queue consumers are deliberately separated from WebSocket
broadcasts so a dashboard cannot steal work from the persistence worker.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field

from .config import settings
from .lancedb_client import LanceDBClient

logger = logging.getLogger(__name__)
QUEUE_MAXSIZE = 1000
mqtt_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
websocket_clients: set[WebSocket] = set()
db_client = LanceDBClient(db_path=settings.LANCEDB_PATH, index_cache_size=settings.LANCEDB_INDEX_CACHE_SIZE)


class Telemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    metrics: dict[str, float | int | bool] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


async def _broadcast(data: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    for client in tuple(websocket_clients):
        try:
            await client.send_json(data)
        except (RuntimeError, WebSocketDisconnect):
            dead.append(client)
    for client in dead:
        websocket_clients.discard(client)


async def _worker() -> None:
    while True:
        item = await mqtt_queue.get()
        try:
            # Persistence remains a prototype path; do not manufacture embeddings.
            if not hasattr(db_client, "insert_telemetry"):
                logger.warning("Telemetry worker received data; persistence adapter is not implemented")
            await _broadcast(item)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telemetry processing failed")
        finally:
            mqtt_queue.task_done()


@asynccontextmanager
async def lifespan(_: FastAPI):
    worker = asyncio.create_task(_worker(), name="yby-telemetry-worker")
    try:
        yield
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker
        for client in tuple(websocket_clients):
            with suppress(Exception):
                await client.close()
        websocket_clients.clear()
        await db_client.close()


app = FastAPI(title="YBY SEED Gateway (prototype)", version="0.2.0", lifespan=lifespan)


@app.post("/telemetry", status_code=202)
async def receive_telemetry(data: Telemetry) -> dict[str, Any]:
    payload = data.model_dump(mode="json")
    try:
        mqtt_queue.put_nowait(payload)
    except asyncio.QueueFull as exc:
        raise HTTPException(status_code=503, detail="Telemetry queue is full") from exc
    return {"status": "queued", "queue_size": mqtt_queue.qsize(), "timestamp": datetime.now(timezone.utc).isoformat()}


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket) -> None:
    await websocket.accept()
    websocket_clients.add(websocket)
    try:
        while True:
            # Keep connection alive; actual events are broadcast by the worker.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        websocket_clients.discard(websocket)


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {"status": "prototype", "queue_size": mqtt_queue.qsize(), "websocket_clients": len(websocket_clients)}
