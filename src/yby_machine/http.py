"""HTTP fino: FastAPI /api/machine/{generate,apps,apps/{app_id},schema}."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.yby_machine.cache import create_translate_cache_from_env
from src.yby_machine.embedder import create_embedder_from_env
from src.yby_machine.pipeline import MachinePipeline
from src.yby_machine.ports import AppSummary
from src.yby_machine.spec import YBYSpec, yby_spec_json_schema
from src.yby_machine.store_pgvector import create_spec_store_from_env
from src.yby_machine.translator import TranslateResult, prompt_to_spec_result


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class GenerateResponse(BaseModel):
    app_id: str | None = None
    spec: YBYSpec
    files: dict[str, str]
    source: str = Field(description="reuse|cache|ollama|litellm|fallback — origem da spec")
    similarity: float | None = None
    created_at: str | None = None


class AppDetailResponse(BaseModel):
    app_id: str
    spec: YBYSpec
    files: dict[str, str]
    source: str
    created_at: str


async def _translate_via_module_hook(prompt: str) -> TranslateResult:
    """Resolve `prompt_to_spec_result` dinamicamente para suportar monkeypatch em testes."""

    return await prompt_to_spec_result(prompt, cache=None)


def _build_default_pipeline() -> MachinePipeline:
    return MachinePipeline(
        embedder=create_embedder_from_env(),
        store=create_spec_store_from_env(),
        cache=create_translate_cache_from_env(),
        translator=_translate_via_module_hook,
    )


def create_app(*, pipeline: MachinePipeline | None = None) -> FastAPI:
    """App FastAPI do YBY Machine com lifespan leve só para fechar adapters opcionais."""

    active_pipeline = pipeline or _build_default_pipeline()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await active_pipeline.close()

    app = FastAPI(title="YBY Machine", version="0.2.0", lifespan=lifespan)
    app.state.pipeline = active_pipeline

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "yby-machine"}

    @app.get("/api/machine/schema")
    async def schema() -> dict[str, Any]:
        """JSON Schema de YBYSpec (útil para clientes e docs)."""

        return yby_spec_json_schema()

    @app.post("/api/machine/generate", response_model=GenerateResponse)
    async def generate(body: GenerateRequest) -> GenerateResponse:
        result = await active_pipeline.generate(body.prompt)
        return GenerateResponse(
            app_id=result.app_id,
            spec=result.spec,
            files=result.files,
            source=result.source,
            similarity=result.similarity,
            created_at=result.created_at,
        )

    @app.get("/api/machine/apps", response_model=list[AppSummary])
    async def list_apps(limit: int = Query(default=50, ge=1, le=200)) -> list[AppSummary]:
        return await active_pipeline.list_apps(limit=limit)

    @app.get("/api/machine/apps/{app_id}", response_model=AppDetailResponse)
    async def get_app(app_id: str) -> AppDetailResponse:
        found = await active_pipeline.get_app(app_id)
        if found is None:
            raise HTTPException(status_code=404, detail="app não encontrado")
        record, files = found
        return AppDetailResponse(
            app_id=record.app_id,
            spec=record.spec,
            files=files,
            source=record.source,
            created_at=record.created_at,
        )

    return app


app = create_app()


def generate_bundle_sync(prompt: str) -> dict[str, Any]:
    """Helper síncrono para CLI/testes (usa fallback se Ollama falhar)."""

    import asyncio

    async def _run() -> GenerateResponse:
        pipeline = _build_default_pipeline()
        try:
            result = await pipeline.generate(prompt)
            return GenerateResponse(
                app_id=result.app_id,
                spec=result.spec,
                files=result.files,
                source=result.source,
                similarity=result.similarity,
                created_at=result.created_at,
            )
        finally:
            await pipeline.close()

    result = asyncio.run(_run())
    return result.model_dump(mode="json")
