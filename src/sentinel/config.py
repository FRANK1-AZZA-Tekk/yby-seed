"""Configuração do Sentinela (JSON + env)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class QuietHours:
    start: str  # HH:MM local wall (interpretado como UTC no MVP se tz omitido)
    end: str


@dataclass(frozen=True)
class SentinelConfig:
    state_dir: Path
    ollama_base_url: str
    ollama_timeout: float
    ollama_down_seconds: float
    backup_dir: Path
    backup_max_age_hours: float
    quiet_hours: QuietHours | None
    check_interval_seconds: float

    @property
    def incidents_path(self) -> Path:
        return self.state_dir / "incidents.json"

    @property
    def runtime_path(self) -> Path:
        return self.state_dir / "runtime.json"


def default_state_dir() -> Path:
    return Path.home() / ".local" / "state" / "yby-seed" / "sentinel"


def load_sentinel_config(
    path: Path | None = None,
    *,
    environ: dict[str, str] | None = None,
) -> SentinelConfig:
    source = environ if environ is not None else dict(os.environ)
    raw_path = path
    if raw_path is None:
        env = source.get("YBY_SENTINEL_CONFIG", "").strip()
        raw_path = Path(env) if env else None

    data: dict[str, Any] = {}
    if raw_path is not None and raw_path.is_file():
        loaded = json.loads(raw_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded

    state = Path(
        str(data.get("state_dir") or source.get("YBY_SENTINEL_STATE") or default_state_dir())
    ).expanduser()

    backup = Path(
        str(
            data.get("backup_dir")
            or source.get("YBY_BACKUP_DIR")
            or (Path.home() / "backups" / "yby-vault")
        )
    ).expanduser()

    quiet = None
    qh = data.get("quiet_hours")
    if isinstance(qh, dict) and qh.get("start") and qh.get("end"):
        quiet = QuietHours(start=str(qh["start"]), end=str(qh["end"]))

    ollama_url = str(
        data.get("ollama_base_url")
        or source.get("YBY_OLLAMA_BASE_URL")
        or "http://127.0.0.1:11434"
    )

    return SentinelConfig(
        state_dir=state,
        ollama_base_url=ollama_url,
        ollama_timeout=float(data.get("ollama_timeout") or source.get("YBY_SENTINEL_OLLAMA_TIMEOUT") or 2.0),
        ollama_down_seconds=float(data.get("ollama_down_seconds") or 300),
        backup_dir=backup,
        backup_max_age_hours=float(data.get("backup_max_age_hours") or 48),
        quiet_hours=quiet,
        check_interval_seconds=float(data.get("check_interval_seconds") or 60),
    )
