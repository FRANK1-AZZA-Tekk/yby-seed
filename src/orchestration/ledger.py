"""Ledger local JSONL do exocórtex (sem Postgres obrigatório)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_LEDGER_PATH = Path("data/exocortex_ledger.jsonl")


def new_decision_id() -> str:
    return uuid.uuid4().hex[:12]


def append_ledger_event(
    event: dict[str, Any],
    *,
    path: Path | None = None,
) -> Path:
    target = path or DEFAULT_LEDGER_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(UTC).isoformat(), **event}
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return target


def read_recent_events(*, limit: int = 20, path: Path | None = None) -> list[dict[str, Any]]:
    target = path or DEFAULT_LEDGER_PATH
    if not target.is_file():
        return []
    lines = target.read_text(encoding="utf-8").strip().splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
