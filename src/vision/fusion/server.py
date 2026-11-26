"""Servidor OpenAI-compatível para inferência FUSION-X."""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.gateway.auth import check_token
from src.vision.fusion.client import FusionClient
from src.vision.fusion.config import FusionConfig

logger = logging.getLogger(__name__)

DEFAULT_INFERENCE_TIMEOUT_S = 120.0


class ChatMessage(BaseModel):
    role: str = "user"
    content: str | list[dict[str, Any]]


class ChatCompletionRequest(BaseModel):
    model: str = "yby-vision"
    messages: list[ChatMessage] = Field(default_factory=list)
    max_tokens: int | None = None
    temperature: float | None = None


_ALLOWED_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"})


def _extract_prompt_and_image_b64(messages: list[ChatMessage]) -> tuple[str, str | None]:
    prompt_parts: list[str] = []
    image_b64: str | None = None
    for message in reversed(messages):
        content = message.content
        if isinstance(content, str):
            prompt_parts.append(content)
            continue
        msg_texts: list[str] = []
        msg_image: str | None = None
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text" and part.get("text"):
                msg_texts.append(str(part["text"]))
            elif part.get("type") == "image_url":
                url = (part.get("image_url") or {}).get("url", "")
                if url.startswith("data:") and "," in url:
                    msg_image = url.split(",", 1)[1]
        if msg_texts:
            prompt_parts.append("\n".join(msg_texts))
        if image_b64 is None and msg_image is not None:
            image_b64 = msg_image
    prompt = "\n".join(reversed(prompt_parts)).strip()
    if not prompt:
        prompt = "Descreva a imagem em detalhes."
    return prompt, image_b64


def _write_temp_image(data: bytes, suffix: str = ".png") -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    path = Path(name)
    path.write_bytes(data)
    return path


def _resolve_fusion_token(explicit_token: str | None) -> str:
    if explicit_token is not None:
        return explicit_token.strip()
    return (os.environ.get("FUSION_API_TOKEN") or os.environ.get("GATEWAY_TOKEN") or "").strip()


def _require_fusion_auth(request: Request, explicit_token: str | None) -> None:
    expected = _resolve_fusion_token(explicit_token)
    ok, status, detail = check_token(request.headers, expected)
    if not ok:
        if status == 503:
            detail = "FUSION_API_TOKEN ou GATEWAY_TOKEN não configurado"
        raise HTTPException(status_code=status, detail=detail)


def create_app(
    client: FusionClient | None = None,
    *,
    inference_timeout_s: float = DEFAULT_INFERENCE_TIMEOUT_S,
    api_token: str | None = None,
) -> FastAPI:
    """Factory FastAPI para testes e produção."""
    fusion_client = client or FusionClient(FusionConfig.from_env(), eager_load=False)
    app = FastAPI(title="YBY FUSION Vision", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> JSONResponse:
        _require_fusion_auth(request, api_token)
        temp_path: Path | None = None
        try:
            content_type = request.headers.get("content-type", "")
            if "multipart/form-data" in content_type:
                try:
                    form = await request.form()
                except RuntimeError as exc:
                    raise HTTPException(
                        status_code=501,
                        detail="Suporte a multipart requer python-multipart instalado.",
                    ) from exc
                image = form.get("image")
                prompt_val = form.get("prompt")
                if image is None or not hasattr(image, "read"):
                    raise HTTPException(status_code=400, detail="Campo 'image' obrigatório.")
                body = await image.read()
                if not body:
                    raise HTTPException(status_code=400, detail="Imagem vazia.")
                raw_suffix = Path(getattr(image, "filename", None) or "upload.png").suffix.casefold()
                suffix = raw_suffix if raw_suffix in _ALLOWED_IMAGE_SUFFIXES else ".png"
                temp_path = _write_temp_image(body, suffix=suffix)
                user_prompt = (
                    prompt_val if isinstance(prompt_val, str) and prompt_val.strip() else "Descreva esta imagem."
                ).strip()
            else:
                try:
                    payload = ChatCompletionRequest.model_validate(await request.json())
                except Exception as exc:  # noqa: BLE001
                    raise HTTPException(status_code=400, detail="Payload JSON inválido.") from exc
                user_prompt, image_b64 = _extract_prompt_and_image_b64(payload.messages)
                if not image_b64:
                    raise HTTPException(
                        status_code=400,
                        detail="Mensagem deve incluir image_url em base64 ou use multipart.",
                    )
                try:
                    image_bytes = base64.b64decode(image_b64, validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise HTTPException(status_code=400, detail="image_url base64 inválido.") from exc
                if not image_bytes:
                    raise HTTPException(status_code=400, detail="Imagem vazia.")
                temp_path = _write_temp_image(image_bytes)

            loop = asyncio.get_running_loop()
            analyze = lambda: fusion_client.analyze(temp_path, user_prompt)  # noqa: E731
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, analyze),
                    timeout=inference_timeout_s,
                )
            except asyncio.TimeoutError as exc:
                raise HTTPException(status_code=504, detail="Tempo esgotado na inferência.") from exc
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail="Imagem não encontrada.") from exc
            except Exception as exc:  # noqa: BLE001
                logger.exception("Falha na inferência FUSION")
                raise HTTPException(status_code=500, detail="Erro na inferência.") from exc

            now = int(time.time())
            return JSONResponse(
                {
                    "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
                    "object": "chat.completion",
                    "created": now,
                    "model": "yby-vision",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": result},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                }
            )
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    return app


app = create_app()


def main() -> None:
    import uvicorn

    host = os.environ.get("FUSION_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("FUSION_SERVER_PORT", "8100"))
    if host not in {"127.0.0.1", "localhost", "::1"} and not _resolve_fusion_token(None):
        raise RuntimeError("FUSION_API_TOKEN ou GATEWAY_TOKEN obrigatório para bind fora de loopback.")
    uvicorn.run("src.vision.fusion.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()