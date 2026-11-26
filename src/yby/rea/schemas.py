"""Schemas Pydantic v2 do módulo REA (engenharia reversa defensiva, somente leitura)."""

from __future__ import annotations

import time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _ReaArtifact(BaseModel):
    """Base: todo artefato REA é privado e só pode ser processado em níveis locais."""

    model_config = ConfigDict(extra="forbid")

    sensitivity: Literal["private"] = "private"
    origin: Literal["rea_artifact"] = "rea_artifact"


class EmbeddedSignature(BaseModel):
    """Assinatura de filesystem/bootloader/imagem embutida em um dump."""

    model_config = ConfigDict(extra="forbid")

    offset: int = Field(..., ge=0)
    name: str = Field(..., max_length=64)
    description: str = Field(default="", max_length=200)
    source: Literal["binwalk", "magic"] = "magic"


class FirmwareInspectionReport(_ReaArtifact):
    """Resultado de `inspect_firmware_binary` (strings já sanitizadas)."""

    report_type: Literal["firmware_inspection"] = "firmware_inspection"
    file_path: str
    size_bytes: int = Field(..., ge=0)
    sha256: str = Field(..., min_length=64, max_length=64)
    file_format: Literal["esp32_image", "elf", "raw"] = "raw"
    architecture: str = "unknown"
    bits: int | None = None
    endianness: Literal["little", "big"] | None = None
    chip: str | None = None
    entropy_overall: float = Field(..., ge=0.0, le=8.0)
    entropy_block_size: int = Field(..., gt=0)
    entropy_blocks: list[float] = Field(default_factory=list)
    high_entropy_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    strings: list[str] = Field(default_factory=list)
    strings_truncated: bool = False
    signatures: list[EmbeddedSignature] = Field(default_factory=list)
    rabin2_info: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class SymbolSummary(BaseModel):
    """Símbolo/função listado por backend estático (nomes e código sanitizados)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., max_length=200)
    address: str = ""
    size: int | None = Field(default=None, ge=0)
    kind: str = Field(default="func", max_length=32)
    signature: str = Field(default="", max_length=300)
    pseudocode: str = Field(default="", max_length=4000)


class DecompileReport(_ReaArtifact):
    """Resultado de `decompile_symbols_headless` (somente leitura, sem execução)."""

    report_type: Literal["decompile"] = "decompile"
    binary_path: str
    backend: str
    symbol_filter: str = ""
    total_symbols: int = Field(default=0, ge=0)
    symbols: list[SymbolSummary] = Field(default_factory=list)
    truncated: bool = False
    notes: list[str] = Field(default_factory=list)


class DiffChunk(BaseModel):
    """Setor de flash (padrão 4 KiB) que difere entre duas imagens."""

    model_config = ConfigDict(extra="forbid")

    offset: int = Field(..., ge=0)
    length: int = Field(..., ge=0)
    base_hash: str | None = None
    target_hash: str | None = None
    base_preview: str = ""
    target_preview: str = ""


class FirmwareDiffReport(_ReaArtifact):
    """Comparação entre dump de fábrica e build customizado do T-Watch S3 Plus."""

    report_type: Literal["firmware_diff"] = "firmware_diff"
    base_path: str
    target_path: str
    base_sha256: str = Field(..., min_length=64, max_length=64)
    target_sha256: str = Field(..., min_length=64, max_length=64)
    base_size: int = Field(..., ge=0)
    target_size: int = Field(..., ge=0)
    size_delta: int
    block_size: int = Field(..., gt=0)
    identical: bool
    changed_blocks: int = Field(default=0, ge=0)
    changed_bytes: int = Field(default=0, ge=0)
    chunks: list[DiffChunk] = Field(default_factory=list)
    truncated: bool = False


ReaReport = Annotated[
    FirmwareInspectionReport | DecompileReport | FirmwareDiffReport,
    Field(discriminator="report_type"),
]


class ReaAnalysisEnvelope(BaseModel):
    """Envelope que viaja pela malha: sempre privado e de origem `rea_artifact`."""

    model_config = ConfigDict(extra="forbid")

    sensitivity: Literal["private"] = "private"
    origin: Literal["rea_artifact"] = "rea_artifact"
    report: ReaReport
    created_at: float = Field(default_factory=time.time)
