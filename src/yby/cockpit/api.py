"""Router FastAPI do Cockpit PhoneBox (`/api/v1/cockpit/status` e `/api/v1/cockpit/webhook`)."""

from __future__ import annotations

import os
from collections.abc import Mapping

from fastapi import APIRouter, FastAPI, HTTPException, Request

from src.gateway.auth import check_token
from src.yby.cockpit.schemas import (
    CockpitStatusResponse,
    CockpitWebhookRequest,
    CockpitWebhookResponse,
)
from src.yby.cockpit.service import CockpitActionError, CockpitService


def _resolve_cockpit_token(
    expected_token: str | None,
    environ: Mapping[str, str] | None = None,
) -> str:
    if expected_token is not None:
        return expected_token.strip()
    source = environ if environ is not None else os.environ
    return source.get("YBY_COCKPIT_TOKEN", "").strip()


def _check_optional_token(request: Request, expected_token: str) -> None:
    """Valida token via `check_token` somente quando `YBY_COCKPIT_TOKEN` estiver definido."""

    if not expected_token:
        return
    ok, status_code, detail = check_token(request.headers, expected_token)
    if not ok:
        raise HTTPException(status_code=status_code, detail=detail)


def create_cockpit_router(
    service: CockpitService,
    *,
    expected_token: str | None = None,
) -> APIRouter:
    """Monta rotas leves do PhoneBox sob `/api/v1/cockpit`."""

    router = APIRouter(prefix="/api/v1/cockpit", tags=["cockpit", "phonebox"])

    @router.get("/status", response_model=CockpitStatusResponse)
    async def cockpit_status() -> CockpitStatusResponse:
        return await service.get_status()

    @router.post("/webhook", response_model=CockpitWebhookResponse)
    async def cockpit_webhook(
        body: CockpitWebhookRequest,
        request: Request,
    ) -> CockpitWebhookResponse:
        _check_optional_token(request, _resolve_cockpit_token(expected_token))
        try:
            return await service.handle_webhook(body)
        except CockpitActionError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return router


def create_cockpit_app(
    *,
    service: CockpitService | None = None,
    expected_token: str | None = None,
) -> FastAPI:
    """Fábrica FastAPI standalone pronta para `uvicorn --factory` do PhoneBox."""

    if service is None:
        from src.yby_machine.store_pgvector import create_spec_store_from_env

        service = CockpitService(spec_store=create_spec_store_from_env())

    app = FastAPI(title="YBY Cockpit PhoneBox Bridge", version="0.2.0")
    app.include_router(create_cockpit_router(service, expected_token=expected_token))
    return app

