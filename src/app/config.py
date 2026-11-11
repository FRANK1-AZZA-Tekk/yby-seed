"""Configuração tipada do hub (env → AppSettings)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppSettings:
    """Settings estáveis para o framework (Function Over Form)."""

    project_root: Path
    data_dir: Path
    llm_provider_preference: str  # "auto" | "ollama" | "openrouter"
    ollama_base_url: str
    ollama_model: str
    openrouter_model: str
    has_openrouter_key: bool
    ux_locale: str  # "pt"
    skills_mode: str  # "dry_run" | "dry_run_safe_auto" | "deferred"
    memory_backend: str  # "none" | "local_files" | "qdrant"


def load_settings(project_root: Path | None = None) -> AppSettings:
    """Carrega `.env` e resolve defaults PC-first."""
    root = project_root or PROJECT_ROOT
    load_dotenv(root / ".env")

    openrouter_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    ollama_base = (
        os.getenv("OLLAMA_BASE_URL")
        or os.getenv("OLLAMA_API_BASE")
        or "http://localhost:11434"
    ).rstrip("/")
    preference = (os.getenv("YBY_LLM_PROVIDER") or "auto").strip().lower()
    if preference not in {"auto", "ollama", "openrouter"}:
        preference = "auto"

    data_dir = Path(os.getenv("YBY_DATA_DIR") or (root / ".yby"))
    skills_mode = (os.getenv("YBY_SKILLS_MODE") or "dry_run").strip().lower()
    if skills_mode not in {"dry_run", "dry_run_safe_auto", "deferred"}:
        skills_mode = "dry_run"
    memory = (os.getenv("YBY_MEMORY_BACKEND") or "none").strip().lower()
    if memory not in {"none", "local_files", "qdrant"}:
        memory = "none"

    return AppSettings(
        project_root=root,
        data_dir=data_dir,
        llm_provider_preference=preference,
        ollama_base_url=ollama_base,
        ollama_model=os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.2:3b"),
        openrouter_model=os.getenv(
            "OPENROUTER_MODEL",
            "openrouter/meta-llama/llama-3.2-3b-instruct:free",
        ),
        has_openrouter_key=bool(openrouter_key),
        ux_locale="pt",
        skills_mode=skills_mode,
        memory_backend=memory,
    )
