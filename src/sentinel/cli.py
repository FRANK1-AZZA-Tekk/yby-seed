"""CLI: yby sentinel — tick local (sem reparo, sem enable automático)."""

from __future__ import annotations

from pathlib import Path

import click


@click.group("sentinel")
def sentinel_cli() -> None:
    """Sentinela local (coletar → avaliar → notificar)."""


@sentinel_cli.command("once")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="JSON do Sentinela (padrão: YBY_SENTINEL_CONFIG).",
)
def sentinel_once(config_path: Path | None) -> None:
    """Uma passagem de coleta/avaliação/notificação."""

    from dotenv import load_dotenv

    from src.sentinel.config import load_sentinel_config
    from src.sentinel.engine import run_once

    load_dotenv(override=False)
    config = load_sentinel_config(config_path)
    result = run_once(config)
    click.echo(
        f"ollama={'ok' if result.probe.ollama_ok else result.probe.ollama_detail} | "
        f"backup={result.probe.backup_status}"
    )
    for note in result.notes:
        click.echo(f"- {note}")
    if result.notified:
        click.echo(f"notificados: {', '.join(result.notified)}")
    if result.pending:
        click.echo(f"pendentes: {', '.join(result.pending)}")


@sentinel_cli.command("rules")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
)
def sentinel_rules(config_path: Path | None) -> None:
    """Lista regras e estado (pausa / incidente ativo)."""

    from dotenv import load_dotenv

    from src.sentinel.config import load_sentinel_config
    from src.sentinel.engine import list_rules

    load_dotenv(override=False)
    config = load_sentinel_config(config_path)
    for row in list_rules(config):
        paused = "pausada" if row["paused"] else "ativa"
        inc = row["active_incident"]
        extra = ""
        if inc:
            extra = f" | incidente={inc['id']} pending={inc['pending_notify']}"
        click.echo(f"{row['id']}: {paused}{extra}")
