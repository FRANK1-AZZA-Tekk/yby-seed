"""App FastAPI modular da Malha de 4 Nós (Módulos A, B e D)."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from src.gateway.auth import check_token
from src.yby.audio.service import AsyncVoicePipeline
from src.yby.bridges.ble_bridge import BleGattBridge
from src.yby.edge_sync.api import create_edge_sync_router
from src.yby.edge_sync.worker import EdgeSyncWorker
from src.yby.rea.mcp_server import ReaPathError, default_firmware_root, resolve_in_root
from src.yby.rea.schemas import ReaAnalysisEnvelope
from src.yby.rea.tools import ReaToolError, build_analysis_envelope, diff_firmware_dumps
from src.yby.routing.router import CognitiveRouter, RoutingExhaustedError
from src.yby.routing.schemas import RouteRequest, RouteResponse


def _resolve_gateway_token(
    expected_token: str | None,
    environ: Mapping[str, str] | None = None,
) -> str:
    if expected_token is not None:
        return expected_token.strip()
    source = environ if environ is not None else os.environ
    return (
        source.get("YBY_EDGE_SYNC_TOKEN")
        or source.get("GATEWAY_TOKEN")
        or ""
    ).strip()


class ReaDiffRequest(BaseModel):
    """Corpo de `POST /rea/diff`: caminhos relativos a `YBY_REA_FIRMWARE_DIR`."""

    model_config = ConfigDict(extra="forbid")

    base_bin: str = Field(..., min_length=1, max_length=256)
    target_bin: str = Field(..., min_length=1, max_length=256)
    block_size: int = Field(default=4096, ge=256, le=1024 * 1024)


def create_mesh_app(
    *,
    router: CognitiveRouter | None = None,
    audio_pipeline: AsyncVoicePipeline | None = None,
    edge_worker: EdgeSyncWorker | None = None,
    expected_token: str | None = None,
    ble_bridge: BleGattBridge | None = None,
    rea_enabled: bool = False,
    rea_firmware_root: str | Path | None = None,
) -> FastAPI:
    """Fábrica testável do servidor HTTP da malha (não altera o gateway legado)."""

    app = FastAPI(title="YBY Mesh Hub (4-Node Local-First)", version="0.2.0")

    def _guard(request: Request) -> None:
        ok, code, detail = check_token(
            request.headers,
            _resolve_gateway_token(expected_token),
        )
        if not ok:
            raise HTTPException(status_code=code, detail=detail)

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "modules": {
                "routing": router is not None,
                "audio": audio_pipeline is not None,
                "edge_sync": edge_worker is not None,
                "ble_bridge": ble_bridge is not None,
                "rea": rea_enabled,
            },
            "audio_state": audio_pipeline.state if audio_pipeline is not None else "disabled",
        }

    if router is not None:

        @app.post("/route", response_model=RouteResponse)
        async def route_endpoint(body: RouteRequest, request: Request) -> RouteResponse:
            _guard(request)
            try:
                return await router.route(body)
            except RoutingExhaustedError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(exc),
                ) from exc

    if audio_pipeline is not None:

        @app.get("/audio/state")
        async def audio_state() -> dict[str, str]:
            return {"state": audio_pipeline.state}

        @app.post("/audio/turn", status_code=status.HTTP_202_ACCEPTED)
        async def trigger_audio_turn(request: Request) -> dict[str, str]:
            _guard(request)
            audio_pipeline.start_turn_background()
            return {"status": "accepted", "state": audio_pipeline.state}

    if ble_bridge is not None:

        @app.get("/bridges/ble/profiles")
        async def ble_profiles(request: Request) -> dict[str, object]:
            _guard(request)
            profiles = await asyncio.to_thread(ble_bridge.list_profiles)
            return {"profiles": [profile.model_dump(mode="json") for profile in profiles]}

    if rea_enabled:
        firmware_root = Path(rea_firmware_root) if rea_firmware_root else default_firmware_root()

        @app.post("/rea/diff", response_model=ReaAnalysisEnvelope)
        async def rea_diff(body: ReaDiffRequest, request: Request) -> ReaAnalysisEnvelope:
            _guard(request)
            try:
                base = resolve_in_root(body.base_bin, firmware_root)
                target = resolve_in_root(body.target_bin, firmware_root)
                report = await asyncio.to_thread(
                    diff_firmware_dumps, base, target, body.block_size
                )
            except ReaPathError as exc:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
            except ReaToolError as exc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
            return build_analysis_envelope(report)

    if edge_worker is not None:
        app.include_router(
            create_edge_sync_router(edge_worker, expected_token=expected_token)
        )

    return app
