"""HTTP fino: FastAPI POST /api/machine/generate → YBYSpec + bundle PWA."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from src.yby_machine.cache import DEFAULT_SPEC_CACHE
from src.yby_machine.compiler import compile_pwa
from src.yby_machine.spec import YBYSpec, yby_spec_json_schema
from src.yby_machine.translator import prompt_to_spec_result


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class GenerateResponse(BaseModel):
    spec: YBYSpec
    files: dict[str, str]
    source: str = Field(description="ollama|fallback — origem da spec")


def create_app() -> FastAPI:
    """App FastAPI do YBY Machine (montar ou rodar com uvicorn)."""

    app = FastAPI(title="YBY Machine", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "yby-machine"}

    @app.get("/api/machine/schema")
    async def schema() -> dict[str, Any]:
        """JSON Schema de YBYSpec (útil para clientes e docs)."""

        return yby_spec_json_schema()

    @app.post("/api/machine/generate", response_model=GenerateResponse)
    async def generate(body: GenerateRequest) -> GenerateResponse:
        result = await prompt_to_spec_result(body.prompt, cache=DEFAULT_SPEC_CACHE)
        files = compile_pwa(result.spec)
        return GenerateResponse(spec=result.spec, files=files, source=result.source)

    return app


app = create_app()


def generate_bundle_sync(prompt: str) -> dict[str, Any]:
    """Helper síncrono para CLI/testes (usa fallback se Ollama falhar)."""

    import asyncio

    async def _run() -> GenerateResponse:
        result = await prompt_to_spec_result(prompt, cache=DEFAULT_SPEC_CACHE)
        return GenerateResponse(
            spec=result.spec,
            files=compile_pwa(result.spec),
            source=result.source,
        )

    result = asyncio.run(_run())
    return result.model_dump(mode="json")
