"""Horário silencioso (HH:MM, janela que pode cruzar meia-noite)."""

from __future__ import annotations

from datetime import datetime

from src.sentinel.config import QuietHours


def parse_hhmm(text: str) -> tuple[int, int]:
    parts = text.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"HH:MM inválido: {text!r}")
    return int(parts[0]), int(parts[1])


def in_quiet_hours(now: datetime, quiet: QuietHours | None) -> bool:
    if quiet is None:
        return False
    hour_min = now.hour * 60 + now.minute
    start_h, start_m = parse_hhmm(quiet.start)
    end_h, end_m = parse_hhmm(quiet.end)
    start = start_h * 60 + start_m
    end = end_h * 60 + end_m
    if start == end:
        return False
    if start < end:
        return start <= hour_min < end
    # cruza meia-noite
    return hour_min >= start or hour_min < end
