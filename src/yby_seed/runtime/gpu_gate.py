"""Semáforo global de inferência local (GTX 1650 — 4 GB VRAM)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

# Compartilhado entre HTTP (`POST /v1/seed/generate`) e MQTT autônomo.
_INFERENCE_SEMAPHORE = asyncio.Semaphore(1)


@asynccontextmanager
async def inference_slot() -> AsyncIterator[None]:
    await _INFERENCE_SEMAPHORE.acquire()
    try:
        yield
    finally:
        _INFERENCE_SEMAPHORE.release()
