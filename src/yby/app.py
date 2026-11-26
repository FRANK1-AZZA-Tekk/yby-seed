"""App FastAPI modular da Malha de 4 Nós (Módulos A, B e D)."""

from __future__ import annotations

import os
from collections.abc import Mapping

from fastapi import FastAPI, HTTPException, Request, status

from src.gateway.auth import check_token
from src.yby.audio.service import AsyncVoicePipeline
from src.yby.edge_sync.api import create_edge_sync_router
from src.yby.edge_sync.worker import EdgeSyncWorker
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


def create_mesh_app(
    *,
    router: CognitiveRouter | None = None,
    audio_pipeline: AsyncVoicePipeline | None = None,
    edge_worker: EdgeSyncWorker | None = None,
    expected_token: str | None = None,
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

    if edge_worker is not None:
        app.include_router(
            create_edge_sync_router(edge_worker, expected_token=expected_token)
        )

    return app
