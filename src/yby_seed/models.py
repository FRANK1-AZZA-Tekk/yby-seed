from typing import Literal

from pydantic import BaseModel, Field

LanguageKind = Literal["python", "cpp_embedded"]
DomainKind = Literal["python_fastapi", "esp_idf", "lvgl_v9", "modbus_rtu"]


class StructuredCode(BaseModel):
    """Resposta estruturada exigida do LiteLLM (JSON)."""

    language: LanguageKind
    filename: str = Field(..., min_length=1, max_length=128)
    code: str = Field(..., min_length=1)
    tests: str | None = Field(
        default=None,
        description="Conteúdo pytest para Python; ignorado em C++ embarcado.",
    )


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system_prompt: str | None = None
    language: LanguageKind | None = None
    domain: DomainKind = "python_fastapi"


class GenerateResponse(BaseModel):
    success: bool
    attempts: int
    code: str | None = None
    filename: str | None = None
    language: LanguageKind | None = None
    stdout: str = ""
    stderr: str = ""
    dataset_saved: bool = False
    mqtt_published: bool = False


class ForgeDryRunRequest(BaseModel):
    mission: Literal["rag-embed", "finetune-qlora", "quantize"] = "rag-embed"
    max_usd: float | None = None
