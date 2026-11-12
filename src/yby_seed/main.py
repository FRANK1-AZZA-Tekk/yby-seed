"""FastAPI — API + UI local YBY SEED."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

from src.yby_seed.agents import mission_progress_queues
from src.yby_seed.engine import SeedEngine
from src.yby_seed.forge import vast_router
from src.yby_seed.mcp.server import mount_mcp_on_fastapi
from src.yby_seed.models import ForgeDryRunRequest, GenerateRequest, GenerateResponse
from src.yby_seed.telemetry import collect_telemetry

UI_INDEX = Path(__file__).resolve().parent / "ui" / "index.html"

app = FastAPI(title="YBY SEED", version="0.1.0")
_engine = SeedEngine()
mount_mcp_on_fastapi(app)


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return UI_INDEX.read_text(encoding="utf-8")


@app.get("/v1/seed/telemetry")
async def telemetry_sse() -> StreamingResponse:
    async def generator():
        while True:
            payload = collect_telemetry()
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.post("/v1/seed/generate", response_model=GenerateResponse)
async def seed_generate(body: GenerateRequest) -> GenerateResponse:
    """Vibe Coding via orquestrador multiagente (Architect → Builder → Sandbox → Auditor)."""
    return await _engine.generate(body)


@app.get("/v1/seed/missions/{mission_id}/events")
async def mission_events(mission_id: str) -> StreamingResponse:
    """SSE de progresso da missão (fila alimentada pelo orquestrador)."""

    async def generator():
        queue = mission_progress_queues.get(mission_id)
        if queue is None:
            yield f"data: {json.dumps({'error': 'mission_not_found'}, ensure_ascii=False)}\n\n"
            return
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=120.0)
            except TimeoutError:
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if event.get("phase") in {"success", "failed"}:
                break

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.post("/v1/seed/forge/dry-run")
async def forge_dry_run(body: ForgeDryRunRequest) -> dict:
    profile = vast_router.MISSION_PROFILES[body.mission]
    max_usd = body.max_usd if body.max_usd is not None else profile["default_max_usd"]
    return vast_router.run_mission(body.mission, max_usd=max_usd, dry_run=True)


def run() -> None:
    import uvicorn

    uvicorn.run("src.yby_seed.main:app", host="127.0.0.1", port=8088, reload=False)


if __name__ == "__main__":
    run()
