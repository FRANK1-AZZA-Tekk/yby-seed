"""Caminhos padrão do Evo (XDG + overrides; reports no repo)."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_REPORTS_DIR = Path("evo/reports")
DEFAULT_DB_NAME = "evo.sqlite3"


def project_root() -> Path:
    """Raiz do repositório (pai de `src/`)."""

    return Path(__file__).resolve().parents[2]


def xdg_data_home() -> Path:
    raw = os.environ.get("XDG_DATA_HOME", "").strip()
    if raw:
        return Path(raw)
    return Path.home() / ".local" / "share"


def resolve_db_path(explicit: Path | str | None = None) -> Path:
    """DB local fora do git.

    Ordem: argumento → `YBY_EVO_DB` → `$XDG_DATA_HOME/yby/evo/evo.sqlite3`
    (fallback `~/.local/share/yby/evo/`).
    """

    if explicit is not None:
        return Path(explicit)
    env = os.environ.get("YBY_EVO_DB", "").strip()
    if env:
        return Path(env)
    return xdg_data_home() / "yby" / "evo" / DEFAULT_DB_NAME


def resolve_reports_dir(explicit: Path | str | None = None) -> Path:
    """Relatórios Markdown em `evo/reports/` na raiz do repo (ou override)."""

    if explicit is not None:
        return Path(explicit)
    env = os.environ.get("YBY_EVO_REPORTS", "").strip()
    if env:
        return Path(env)
    return project_root() / DEFAULT_REPORTS_DIR


def cloud_usage_log_path() -> Path:
    """Só leitura do JSONL existente (nunca escreve / nunca chama nuvem)."""

    raw = os.environ.get("YBY_CLOUD_LOG_PATH", "logs/cloud_usage.jsonl").strip()
    path = Path(raw or "logs/cloud_usage.jsonl")
    if not path.is_absolute():
        path = project_root() / path
    return path
