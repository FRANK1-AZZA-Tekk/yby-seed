"""Coleta somente leitura — não reinicia Ollama nem toca no vault."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable

from src.platform.hub import check_ollama
from src.sentinel.config import SentinelConfig
from src.sentinel.models import ProbeSnapshot

OllamaProbe = Callable[[str, float], str]


def collect(
    config: SentinelConfig,
    *,
    ollama_probe: OllamaProbe | None = None,
    now: datetime | None = None,
) -> ProbeSnapshot:
    probe = ollama_probe or (
        lambda url, timeout: check_ollama(url, timeout=timeout)
    )
    detail = probe(config.ollama_base_url, config.ollama_timeout)
    ollama_ok = detail == "ok"

    backup_status, backup_detail, age = inspect_backup(
        config.backup_dir,
        max_age_hours=config.backup_max_age_hours,
        now=now or datetime.now(timezone.utc),
    )
    return ProbeSnapshot(
        ollama_ok=ollama_ok,
        ollama_detail=detail,
        backup_status=backup_status,
        backup_detail=backup_detail,
        backup_age_hours=age,
    )


def inspect_backup(
    backup_dir: Path,
    *,
    max_age_hours: float,
    now: datetime,
) -> tuple[str, str, float | None]:
    """Devolve (ok|stale|unverified, detalhe, age_hours?)."""

    try:
        if not backup_dir.exists():
            return "unverified", f"diretório ausente: {backup_dir}", None
        if not backup_dir.is_dir():
            return "unverified", f"não é diretório: {backup_dir}", None
        archives = sorted(backup_dir.glob("yby-vault-*.tar.gz"))
        if not archives:
            return "unverified", f"nenhum arquivo yby-vault-*.tar.gz em {backup_dir}", None
        newest = max(archives, key=lambda p: p.stat().st_mtime)
        mtime = datetime.fromtimestamp(newest.stat().st_mtime, tz=timezone.utc)
        age_hours = (now - mtime).total_seconds() / 3600.0
        if age_hours > max_age_hours:
            return (
                "stale",
                f"backup mais antigo que {max_age_hours:g}h "
                f"(idade≈{age_hours:.1f}h; arquivo={newest.name})",
                age_hours,
            )
        return "ok", f"backup ok (idade≈{age_hours:.1f}h; {newest.name})", age_hours
    except OSError as exc:
        return "unverified", f"não consegui verificar o backup: {exc}", None
