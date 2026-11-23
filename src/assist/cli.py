"""Click: `yby assist` — sessão texto PT-BR."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from dotenv import load_dotenv

from src.assist.config import load_assist_config
from src.assist.router import OllamaAssistPlanner
from src.assist.session import AssistSession
from src.engine.config import EngineConfig
from src.engine.providers import OllamaProvider


@click.command("assist")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="JSON de apps/pastas/rotinas (padrão: YBY_ASSIST_CONFIG).",
)
def assist_cli(config_path: Path | None) -> None:
    """Sessão local para ferramentas cadastradas do PC (sem nuvem).

    Lembretes só avisam enquanto esta sessão estiver aberta.
    Rotinas por alias exato funcionam mesmo se o Ollama estiver fora.
    """

    load_dotenv(override=False)
    config = load_assist_config(config_path)
    eng = EngineConfig.from_env()
    planner = OllamaAssistPlanner(
        OllamaProvider(config.ollama_base_url, timeout=config.ollama_timeout),
        model=eng.local_model,
    )

    def confirm_fn(message: str) -> bool:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            click.echo("Sem TTY — confirmação negada.", err=True)
            return False
        click.echo(message)
        answer = click.prompt("Confirma", default="n", show_default=True)
        return answer.strip().casefold() in {"s", "sim", "y", "yes"}

    session = AssistSession(
        config=config,
        planner=planner,
        confirm_fn=confirm_fn,
    )

    click.echo("YBY assist (texto). Digite 'ajuda', 'cancela' ou 'sair'.")
    for msg in session.startup_messages():
        click.echo(msg)

    while True:
        try:
            line = click.prompt("assist", prompt_suffix="> ")
        except (EOFError, KeyboardInterrupt):
            click.echo("\nEncerrado.")
            break
        outcome = session.handle(line)
        if outcome.user_message == "__EXIT__":
            click.echo("Até logo.")
            break
        click.echo(outcome.user_message)
