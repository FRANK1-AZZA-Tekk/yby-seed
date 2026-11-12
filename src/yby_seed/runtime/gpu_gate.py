"""Semáforo global de inferência local (GTX 1650 — 4 GB VRAM)."""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator

# Compartilhado entre HTTP, MQTT, dataset_synth, ingest e MCP embeddings.
_INFERENCE_LOCK = threading.Lock()


@contextmanager
def sync_inference_slot() -> Iterator[None]:
    with _INFERENCE_LOCK:
        yield


@asynccontextmanager
async def inference_slot() -> AsyncIterator[None]:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _INFERENCE_LOCK.acquire)
    try:
        yield
    finally:
        _INFERENCE_LOCK.release()
