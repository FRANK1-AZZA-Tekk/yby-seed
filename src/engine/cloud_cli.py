"""Click: `yby cloud report|prune` (FinOps S5 / #42)."""

from __future__ import annotations

import os
from pathlib import Path

import click
from dotenv import load_dotenv

from src.engine.cloud_usage_db import (
    DEFAULT_DB_PATH,
    CloudUsageRegistry,
    retention_days_from_env,
)
from src.engine.cloud_usage_report import (
    build_cloud_usage_report,
    format_cloud_usage_report,
)


@click.group("cloud")
def cloud_cli() -> None:
    """FinOps local — relatório e retenção (sem rede)."""


@cloud_cli.command("report")
def report_cmd() -> None:
    """Mostra uso/orçamento local (SQLite + limites)."""

    load_dotenv(override=False)
    report = build_cloud_usage_report()
    click.echo(format_cloud_usage_report(report), nl=False)


@cloud_cli.command("prune")
@click.option(
    "--days",
    type=int,
    default=None,
    help="Retenção em dias (padrão: YBY_CLOUD_RETENTION_DAYS ou 90).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Só conta candidatos; não apaga.",
)
def prune_cmd(days: int | None, dry_run: bool) -> None:
    """Apaga completed/failed antigos no registry SQLite."""

    load_dotenv(override=False)
    source = os.environ
    db_raw = source.get("YBY_CLOUD_DB_PATH", DEFAULT_DB_PATH).strip()
    if db_raw.casefold() in {"", "0", "off", "-", "none"}:
        click.echo("SQLite desligado (YBY_CLOUD_DB_PATH=off).", err=True)
        raise SystemExit(1)
    if not db_raw:
        db_raw = DEFAULT_DB_PATH
    db_path = Path(db_raw)
    if not db_path.is_file():
        click.echo(f"DB ausente: {db_path}", err=True)
        raise SystemExit(1)

    retention = days if days is not None else retention_days_from_env(source)
    reg = CloudUsageRegistry(db_path)
    try:
        n = reg.prune(retention_days=retention, dry_run=dry_run)
    finally:
        reg.close()

    action = "candidatos" if dry_run else "apagados"
    click.echo(f"prune: {n} {action} (retention_days={retention})")
