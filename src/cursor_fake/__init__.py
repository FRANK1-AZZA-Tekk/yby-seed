"""Adaptador Cursor fake (lote 18). Dry-run local; sem MCP."""

from src.cursor_fake.adapter import CursorFakeError, format_report, simulate
from src.cursor_fake.schemas import DryRunReport, SimulatedStep

__all__ = [
    "CursorFakeError",
    "DryRunReport",
    "SimulatedStep",
    "format_report",
    "simulate",
]
