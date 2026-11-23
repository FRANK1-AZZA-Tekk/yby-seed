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

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

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


def _extract_prompt_and_image_b64(messages: list[ChatMessage]) -> tuple[str, str | None]:
    prompt_parts: list[str] = []
    image_b64: str | None = None
    for message in reversed(messages):
        content = message.content
        if isinstance(content, str):
            prompt_parts.append(content)
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text" and part.get("text"):
                prompt_parts.append(str(part["text"]))
            elif part.get("type") == "image_url":
                url = (part.get("image_url") or {}).get("url", "")
                if url.startswith("data:") and "," in url:
                    image_b64 = url.split(",", 1)[1]
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


def create_app(
    client: FusionClient | None = None,
    *,
    inference_timeout_s: float = DEFAULT_INFERENCE_TIMEOUT_S,
) -> FastAPI:
    """Factory FastAPI para testes e produção."""
    fusion_client = client or FusionClient(FusionConfig.from_env(), eager_load=False)
    app = FastAPI(title="YBY FUSION Vision", version="0.1.0")

    @app.post("/v1/chat/completions")
    async def chat_completions(
        request: Request,
        image: UploadFile | None = File(None),
        prompt: str | None = Form(None),
    ) -> JSONResponse:
        temp_path: Path | None = None
        try:
            content_type = request.headers.get("content-type", "")
            if "multipart/form-data" in content_type:
                if image is None:
                    raise HTTPException(status_code=400, detail="Campo 'image' obrigatório.")
                body = await image.read()
                if not body:
                    raise HTTPException(status_code=400, detail="Imagem vazia.")
                suffix = Path(image.filename or "upload.png").suffix or ".png"
                temp_path = _write_temp_image(body, suffix=suffix)
                user_prompt = (prompt or "Descreva esta imagem.").strip()
            else:
                try:
                    payload = ChatCompletionRequest.model_validate(await request.json())
                except Exception as exc:  # noqa: BLE001
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
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
                temp_path = _write_temp_image(image_bytes)

            loop = asyncio.get_event_loop()
            analyze = lambda: fusion_client.analyze(temp_path, user_prompt)  # noqa: E731
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, analyze),
                    timeout=inference_timeout_s,
                )
            except asyncio.TimeoutError as exc:
                raise HTTPException(status_code=504, detail="Tempo esgotado na inferência.") from exc
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
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
    uvicorn.run("src.vision.fusion.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()