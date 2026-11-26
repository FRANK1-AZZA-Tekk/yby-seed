"""Módulo REA — engenharia reversa defensiva e somente leitura (sempre `private`).

O servidor/cliente MCP vive em `src.yby.rea.mcp_server` (importe-o diretamente).
"""

from __future__ import annotations

from src.yby.rea.sanitizer import (
    sanitize_binary_strings,
    sanitize_untrusted_text,
    wrap_untrusted_artifact,
)
from src.yby.rea.schemas import (
    DecompileReport,
    DiffChunk,
    EmbeddedSignature,
    FirmwareDiffReport,
    FirmwareInspectionReport,
    ReaAnalysisEnvelope,
    SymbolSummary,
)
from src.yby.rea.tools import (
    ReaToolError,
    build_analysis_envelope,
    build_private_route_request,
    decompile_symbols_headless,
    diff_firmware_dumps,
    inspect_firmware_binary,
)

__all__ = [
    "DecompileReport",
    "DiffChunk",
    "EmbeddedSignature",
    "FirmwareDiffReport",
    "FirmwareInspectionReport",
    "ReaAnalysisEnvelope",
    "ReaToolError",
    "SymbolSummary",
    "build_analysis_envelope",
    "build_private_route_request",
    "decompile_symbols_headless",
    "diff_firmware_dumps",
    "inspect_firmware_binary",
    "sanitize_binary_strings",
    "sanitize_untrusted_text",
    "wrap_untrusted_artifact",
]
