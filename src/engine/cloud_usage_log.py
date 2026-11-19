"""Log local de uso de nuvem — façade JSONL + SQLite (S1 / #42).

API pública estável: `CloudUsageLog.append`. Com registry habilitado escreve
SQLite primeiro; espelha JSONL se `YBY_CLOUD_JSONL_MIRROR=1` (default na migração).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from src.engine.cloud_usage_db import DEFAULT_DB_PATH, CloudUsageRegistry

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
EVENT_EXCEPTION_GRANTED = "cloud_exception_granted"

FORBIDDEN_KEYS = frozenset({"prompt", "api_key", "response", "text", "audio"})


class CloudUsageLog:
    def __init__(
        self,
        path: Path,
        *,
        registry: CloudUsageRegistry | None = None,
        jsonl_mirror: bool = True,
        db_enabled: bool = True,
    ) -> None:
        self.path = path
        self.registry = registry
        self.jsonl_mirror = jsonl_mirror
        self.db_enabled = db_enabled
        self._migrated = False

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> CloudUsageLog:
        source = environ if environ is not None else os.environ
        raw = source.get("YBY_CLOUD_LOG_PATH", DEFAULT_LOG_PATH).strip() or DEFAULT_LOG_PATH
        db_raw = source.get("YBY_CLOUD_DB_PATH", DEFAULT_DB_PATH).strip()
        # Path vazio ou "-" desliga SQLite (só JSONL legado).
        db_enabled = db_raw.casefold() not in {"", "0", "off", "-", "none"}
        if not db_raw:
            db_raw = DEFAULT_DB_PATH
        mirror = _bool(source, "YBY_CLOUD_JSONL_MIRROR", True)
        registry = CloudUsageRegistry(Path(db_raw)) if db_enabled else None
        return cls(
            Path(raw),
            registry=registry,
            jsonl_mirror=mirror,
            db_enabled=db_enabled,
        )

    def append(self, event: dict[str, Any]) -> None:
        missing = REQUIRED_FIELDS - set(event.keys())
        if missing:
            msg = f"evento de nuvem incompleto: faltam {sorted(missing)}"
            raise ValueError(msg)
        for key in FORBIDDEN_KEYS:
            if key in event:
                raise ValueError(f"campo proibido no log: {key}")

        if self.db_enabled and self.registry is not None:
            self._ensure_migrated()
            self.registry.insert_event(event)
            if self.jsonl_mirror:
                self._append_jsonl(event)
            return

        self._append_jsonl(event)

    def _ensure_migrated(self) -> None:
        if self._migrated or self.registry is None:
            return
        self._migrated = True
        self.registry.import_jsonl_if_empty(self.path)

    def _append_jsonl(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        fd = os.open(self.path, flags, 0o600)
        try:
            handle = os.fdopen(fd, "a", encoding="utf-8")
        except Exception:
            os.close(fd)
            raise
        with handle:
            handle.write(line + "\n")
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


def _bool(source: dict[str, str], name: str, default: bool) -> bool:
    raw = source.get(name, "").strip().casefold()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "sim"}
