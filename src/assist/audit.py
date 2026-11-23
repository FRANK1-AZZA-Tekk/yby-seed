"""Log local de metadados do assist (sem corpo de documentos)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def append_audit(
    path: Path,
    *,
    tool: str,
    ok: bool,
    error: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": time.time(),
        "tool": tool,
        "ok": ok,
        "error": error,
        "meta": meta or {},
    }
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
