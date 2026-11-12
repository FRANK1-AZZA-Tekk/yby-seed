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
    validation_report: dict | None = None


class ForgeDryRunRequest(BaseModel):
    mission: Literal["rag-embed", "finetune-qlora", "quantize"] = "rag-embed"
    max_usd: float | None = None


class SerialPortInfo(BaseModel):
    path: str
    label: str
    chipset: str
    suggested_board: str | None = None


class HardwarePortsResponse(BaseModel):
    devices: list[SerialPortInfo]


class ExportRequest(BaseModel):
    target_board: str = "esp32_s3_devkitc1"
    mission: dict | None = Field(
        default=None,
        description="Payload MissionState opcional; se ausente, usa última missão validada.",
    )


class ExportResponse(BaseModel):
    export_path: str
    archive_name: str
    download_url: str


class EconomyStatsResponse(BaseModel):
    total_missions: int
    local_missions: int
    cloud_missions: int
    local_pct: float
    cloud_pct: float
    estimated_savings_usd: float
    ledger_cloud_cost_usd: float
    monthly_spend_usd: float
    budget_cap_usd: float
    budget_remaining_usd: float
    validated_pairs: int
    gpu_profile: str
