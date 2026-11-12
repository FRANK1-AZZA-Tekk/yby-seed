"""FastAPI — API + UI local YBY SEED."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

from src.yby_seed.agents import mission_progress_queues
from src.yby_seed.agents.orchestrator import last_successful_mission
from src.yby_seed.agents.state import MissionState, MissionStatus
from src.yby_seed.daemon.mqtt_listener import MqttAutonomyWorker
from src.yby_seed.engine import SeedEngine
from src.yby_seed.exporter import (
    export_validated_project,
    scan_serial_devices,
    serial_devices_to_json,
)
from src.yby_seed.exporter.project_builder import EXPORT_ROOT
from src.yby_seed.forge import vast_router
from src.yby_seed.mcp.server import mount_mcp_on_fastapi
from src.yby_seed.memory.ledger import get_economy_stats
from src.yby_seed.models import (
    EconomyStatsResponse,
    ExportRequest,
    ExportResponse,
    ForgeDryRunRequest,
    GenerateRequest,
    GenerateResponse,
    HardwarePortsResponse,
    SerialPortInfo,
)
from src.yby_seed.runtime import resources
from src.yby_seed.telemetry import collect_telemetry

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
UI_INDEX = Path(__file__).resolve().parent / "ui" / "index.html"
_engine: SeedEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine
    await resources.startup()
    _engine = SeedEngine(client=resources.build_openai_client())
    worker = MqttAutonomyWorker(engine=_engine)
    await worker.start()
    logger.info("YBY SEED: worker MQTT autônomo ativo")
    yield
    await worker.stop()
    await resources.shutdown()
    _engine = None
    logger.info("YBY SEED: worker MQTT encerrado")


app = FastAPI(title="YBY SEED", version="0.1.0", lifespan=lifespan)
mount_mcp_on_fastapi(app)


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return await asyncio.to_thread(UI_INDEX.read_text, encoding="utf-8")


@app.get("/v1/seed/telemetry")
async def telemetry_sse() -> StreamingResponse:
    async def generator():
        while True:
            payload = await asyncio.to_thread(collect_telemetry)
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.post("/v1/seed/generate", response_model=GenerateResponse)
async def seed_generate(body: GenerateRequest) -> GenerateResponse:
    """Vibe Coding via orquestrador multiagente (Architect → Builder → Sandbox → Auditor)."""
    if _engine is None:
        raise RuntimeError("engine não inicializado")
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


@app.get("/v1/seed/hardware/ports", response_model=HardwarePortsResponse)
async def hardware_ports() -> HardwarePortsResponse:
    devices = await scan_serial_devices()
    return HardwarePortsResponse(
        devices=[SerialPortInfo(**item) for item in serial_devices_to_json(devices)]
    )


@app.post("/v1/seed/export", response_model=ExportResponse)
async def export_project(body: ExportRequest) -> ExportResponse:
    if body.mission:
        state = MissionState.model_validate(body.mission)
    elif last_successful_mission is not None:
        state = last_successful_mission
    else:
        raise HTTPException(status_code=409, detail="nenhuma_missao_validada")

    if state.status != MissionStatus.SUCCESS or state.generated_code is None:
        raise HTTPException(status_code=400, detail="missao_nao_exportavel")

    folder, archive_name = await asyncio.to_thread(
        export_validated_project,
        state,
        body.target_board,
    )
    return ExportResponse(
        export_path=str(folder),
        archive_name=archive_name,
        download_url=f"/v1/seed/export/{archive_name}",
    )


@app.get("/v1/seed/export/{archive_name}")
async def download_export(archive_name: str) -> FileResponse:
    if ".." in archive_name or "/" in archive_name:
        raise HTTPException(status_code=400, detail="nome_invalido")
    path = EXPORT_ROOT / archive_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="arquivo_nao_encontrado")
    return FileResponse(
        path,
        media_type="application/zip",
        filename=archive_name,
    )


@app.get("/v1/seed/stats", response_model=EconomyStatsResponse)
async def seed_stats() -> EconomyStatsResponse:
    payload = await get_economy_stats()
    return EconomyStatsResponse(**payload)


@app.get("/v1/seed/exocortex/recent")
async def exocortex_recent(limit: int = 20) -> dict:
    """Últimos eventos do ledger JSONL do CLI (`yby skill`)."""
    from src.orchestration.ledger import read_recent_events

    capped = max(1, min(limit, 100))
    events = await asyncio.to_thread(read_recent_events, limit=capped)
    return {"events": events, "limit": capped}


@app.post("/v1/seed/forge/dry-run")
async def forge_dry_run(body: ForgeDryRunRequest) -> dict:
    profile = vast_router.MISSION_PROFILES[body.mission]
    max_usd = body.max_usd if body.max_usd is not None else profile["default_max_usd"]
    return await asyncio.to_thread(
        vast_router.run_mission,
        body.mission,
        max_usd=max_usd,
        dry_run=True,
    )


def run() -> None:
    import uvicorn

    uvicorn.run("src.yby_seed.main:app", host="127.0.0.1", port=8088, reload=False)


if __name__ == "__main__":
    run()
