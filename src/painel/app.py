"""FastAPI do painel — bind só em loopback; sem endpoints de execução."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from src.painel.auth import check_token, painel_token_from_env
from src.painel.html import render_resumo
from src.painel.readers import load_resumo


def assert_loopback_host(host: str) -> str:
    """Recusa bind fora de loopback."""

    normalized = (host or "").strip().lower()
    if normalized in {"127.0.0.1", "localhost", "::1"}:
        return "127.0.0.1" if normalized != "::1" else "::1"
    raise ValueError(f"painel só aceita loopback (recebido: {host!r})")


def create_app(
    *,
    token: str | None = None,
    state_dir: Path | None = None,
    develop_plans_dir: Path | None = None,
    audit_path: Path | None = None,
    reminders_path: Path | None = None,
    incidents_path: Path | None = None,
    ollama_probe: Callable[[], str] | None = None,
) -> FastAPI:
    app = FastAPI(title="YBY Painel", docs_url=None, redoc_url=None)
    expected = token if token is not None else painel_token_from_env()

    def _authorized(request: Request) -> Response | None:
        ok, status, msg = check_token(request.headers, expected)
        if ok:
            return None
        return JSONResponse({"error": msg}, status_code=status)

    def _resumo():
        return load_resumo(
            state_dir=state_dir,
            develop_plans_dir=develop_plans_dir,
            audit_path=audit_path,
            reminders_path=reminders_path,
            incidents_path=incidents_path,
            ollama_probe=ollama_probe,
        )

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> Response:
        denied = _authorized(request)
        if denied is not None:
            return denied
        html = render_resumo(_resumo())
        return HTMLResponse(html)

    @app.get("/api/resumo")
    def api_resumo(request: Request) -> Response:
        denied = _authorized(request)
        if denied is not None:
            return denied
        return JSONResponse(_resumo().to_dict())

    return app
