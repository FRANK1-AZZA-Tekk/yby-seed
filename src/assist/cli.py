"""Click: `yby assist` — sessão texto ou voz (pressionar para falar)."""

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
@click.option(
    "--voice/--no-voice",
    default=False,
    help="Pressionar para falar (Whisper/Piper locais). Mesma sessão do texto.",
)
def assist_cli(config_path: Path | None, voice: bool) -> None:
    """Sessão local para ferramentas cadastradas do PC (sem nuvem).

    Lembretes: o assist só cadastra; entrega via `reminders once`.
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

    if voice:
        from src.assist.voice_loop import run_voice_session, voice_available
        from src.voice.config import voice_config_from_env

        vcfg = voice_config_from_env()
        ok, msg = voice_available(vcfg)
        if not ok:
            click.echo(msg, err=True)
            click.echo(
                "Texto continua disponível: python yby.py assist",
                err=True,
            )
            raise SystemExit(1)
        if msg != "voz pronta":
            click.echo(msg, err=True)

        def _wait(_prompt: str = "") -> str:
            return click.get_text_stream("stdin").readline()

        run_voice_session(
            session,
            vcfg,
            input_fn=_wait,
            output_fn=click.echo,
            err_fn=lambda m: click.echo(m, err=True),
        )
        return

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
