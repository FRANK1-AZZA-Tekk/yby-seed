"""Rotas FastAPI do Módulo D protegidas por `check_token` (`src/gateway/auth.py`)."""

from __future__ import annotations

import os
from collections.abc import Mapping

from fastapi import APIRouter, HTTPException, Request

from src.gateway.auth import check_token
from src.yby.edge_sync.schemas import (
    EdgeSyncBatchRequest,
    EdgeSyncBatchResponse,
    EdgeSyncStatus,
)
from src.yby.edge_sync.worker import EdgeSyncWorker


def _resolve_token(expected_token: str | None, environ: Mapping[str, str] | None = None) -> str:
    if expected_token is not None:
        return expected_token.strip()
    source = environ if environ is not None else os.environ
    return (
        source.get("YBY_EDGE_SYNC_TOKEN")
        or source.get("GATEWAY_TOKEN")
        or ""
    ).strip()


def _require_auth(request: Request, expected_token: str) -> None:
    ok, status_code, detail = check_token(request.headers, expected_token)
    if not ok:
        raise HTTPException(status_code=status_code, detail=detail)


def create_edge_sync_router(
    worker: EdgeSyncWorker,
    *,
    expected_token: str | None = None,
) -> APIRouter:
    """Monta `/edge/health`, `/edge/sync`, `/edge/sync/status` e `/edge/sync/drain`."""

    router = APIRouter(prefix="/edge", tags=["edge-sync"])

    @router.get("/health")
    async def edge_health() -> dict[str, object]:
        return {
            "status": "ok",
            "store_backend": worker.primary_store.backend_name,
        }

    @router.post("/sync", response_model=EdgeSyncBatchResponse)
    async def edge_sync(
        batch: EdgeSyncBatchRequest,
        request: Request,
    ) -> EdgeSyncBatchResponse:
        _require_auth(request, _resolve_token(expected_token))
        return await worker.ingest_batch(batch)

    @router.get("/sync/status", response_model=EdgeSyncStatus)
    async def edge_sync_status(request: Request) -> EdgeSyncStatus:
        _require_auth(request, _resolve_token(expected_token))
        return await worker.status()

    @router.post("/sync/drain")
    async def edge_sync_drain(request: Request) -> dict[str, int]:
        _require_auth(request, _resolve_token(expected_token))
        return await worker.drain_fallback()

    return router
