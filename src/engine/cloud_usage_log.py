"""Log local JSONL de uso de nuvem (metadados apenas; sem prompt/chaves)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

DEFAULT_LOG_PATH = "logs/cloud_usage.jsonl"

REQUIRED_FIELDS = frozenset(
    {
        "timestamp",
        "provider",
        "model",
        "purpose",
        "input_tokens_estimate",
        "output_tokens_estimate",
        "result",
    }
)

EVENT_REQUESTED = "cloud_requested"
EVENT_CONFIRMED = "cloud_confirmed"
EVENT_COMPLETED = "cloud_completed"
EVENT_FAILED = "cloud_failed"
EVENT_CANCELLED = "cloud_cancelled"
EVENT_BLOCKED_LOCAL_ONLY = "cloud_blocked_local_only"
EVENT_BLOCKED_BUDGET = "cloud_blocked_budget"
EVENT_BLOCKED_NO_TTY = "cloud_blocked_no_tty"


class CloudUsageLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> CloudUsageLog:
        source = environ if environ is not None else os.environ
        raw = source.get("YBY_CLOUD_LOG_PATH", DEFAULT_LOG_PATH).strip() or DEFAULT_LOG_PATH
        return cls(Path(raw))

    def append(self, event: dict[str, Any]) -> None:
        missing = REQUIRED_FIELDS - set(event.keys())
        if missing:
            msg = f"evento de nuvem incompleto: faltam {sorted(missing)}"
            raise ValueError(msg)
        for key in ("prompt", "api_key", "response", "text", "audio"):
            if key in event:
                raise ValueError(f"campo proibido no log: {key}")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        fd = os.open(self.path, flags, 0o600)
        try:
            with os.fdopen(fd, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except Exception:
            os.close(fd)
            raise
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @staticmethod
    def estimate_tokens(text: str) -> int:
        stripped = text.strip()
        if not stripped:
            return 0
        return max(1, len(stripped) // 4)


def utc_timestamp() -> float:
    return time.time()
