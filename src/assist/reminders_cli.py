"""CLI: yby reminders — entrega em segundo plano (sem sessão)."""

from __future__ import annotations

from pathlib import Path

import click


@click.group("reminders")
def reminders_cli() -> None:
    """Entrega de lembretes cadastrados pelo assist."""


@reminders_cli.command("once")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="JSON do assist (padrão: YBY_ASSIST_CONFIG) — path e quiet hours.",
)
def reminders_once(config_path: Path | None) -> None:
    """Uma passagem: verifica vencidos e notifica (sem stdin)."""

    from dotenv import load_dotenv

    from src.assist.config import load_assist_config
    from src.assist.delivery import deliver_due
    from src.assist.reminders import ReminderStore
    from src.sentinel.config import QuietHours

    load_dotenv(override=False)
    config = load_assist_config(config_path)
    quiet = None
    if config.reminder_quiet_hours is not None:
        quiet = QuietHours(
            start=config.reminder_quiet_hours[0],
            end=config.reminder_quiet_hours[1],
        )
    store = ReminderStore(config.reminders_path)
    result = deliver_due(store, quiet_hours=quiet)
    click.echo(
        f"notificados={len(result.notified)} pendentes={len(result.pending)}"
    )
    for note in result.notes:
        click.echo(f"- {note}")
