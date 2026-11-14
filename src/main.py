#!/usr/bin/env python3
"""
YBY SEED - Ponto de Entrada Principal

Uso:
    python yby.py ask "..."
    python yby.py ask --voice
    python yby.py listen
    python yby.py run "ls"
    python yby.py gate "rm arquivo"

Comandos:
    ask     - Responde em texto (sem shell); --voice grava, pergunta e fala
    listen  - Push-to-talk: grava até Enter → ask → TTS
    hub     - Keepalive do PC Hub (saúde do Ollama)
    run     - Executa comando após a porta de segurança
    gate    - Só decide; não executa
    note    - Grava nota no vault
    recall  - Busca no vault
    agent   - Loop de agente P0 (opt-in; não altera o ask)
"""

import json
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from loguru import logger

from src.actions.runner import DEFAULT_TIMEOUT, run_command
from src.agent_loop.loop import ControlledAgentLoop
from src.agent_loop.planner import OllamaJsonPlanner, ScriptedPlanner
from src.agent_loop.tools import vault_registry_or_skip
from src.engine.config import EngineConfig
from src.engine.hybrid import HybridEngine, engine_from_env
from src.engine.providers import OllamaProvider
from src.memory.vault import VaultError, vault_from_env
from src.platform.hub import main as hub_main
from src.safety.policy import confirm, decide, default_policy_path, load_policy
from src.voice.config import voice_config_from_env
from src.voice.session import VoiceError, listen_once

# Configura logging
logger.add("logs/yby_seed_{time}.log", rotation="1 day", retention="7 days")


@click.group()
def cli():
    """YBY SEED - Programação em Linguagem Natural"""
    pass


@cli.command(
    "run",
    context_settings={"ignore_unknown_options": True, "allow_interspersed_args": False},
)
@click.option(
    "--timeout",
    default=DEFAULT_TIMEOUT,
    show_default=True,
    type=float,
    help="Segundos máximos do subprocesso.",
)
@click.argument("comando", nargs=-1, required=True, type=click.UNPROCESSED)
def run_cmd(timeout: float, comando: tuple[str, ...]) -> None:
    """Executa um comando só se a porta de segurança permitir.

    Allowlist roda direto. Fora dela, pergunta s/n. Recusa nunca executa.
    """

    texto = " ".join(comando).strip()
    if not texto:
        click.echo('Informe um comando. Exemplo: yby run "ls"', err=True)
        raise SystemExit(1)

    policy = load_policy(default_policy_path())
    project_root = default_policy_path().parents[1]
    result = run_command(
        texto,
        policy=policy,
        project_root=project_root,
        timeout=timeout,
        input_fn=lambda: click.prompt("s/n", prompt_suffix=" "),
        output_fn=click.echo,
    )

    if not result.approved:
        raise SystemExit(1)

    if result.stdout:
        click.echo(result.stdout, nl=False)
        if not result.stdout.endswith("\n"):
            click.echo()
    if result.stderr:
        click.echo(result.stderr, err=True, nl=False)
        if not result.stderr.endswith("\n"):
            click.echo(err=True)

    if result.timed_out:
        click.echo(f"timeout após {timeout:g}s", err=True)
        raise SystemExit(124)
    raise SystemExit(0 if result.exit_code == 0 else (result.exit_code or 1))


@cli.command()
@click.option(
    "--heavy",
    is_flag=True,
    help="Força a nuvem, mesmo num pedido curto.",
)
@click.option(
    "--voice/--no-voice",
    default=False,
    help="Grava até Enter, pergunta ao motor e fala a resposta (Piper).",
)
@click.argument("pergunta", nargs=-1, required=False)
def ask(heavy: bool, voice: bool, pergunta: tuple[str, ...]) -> None:
    """Responde um pedido em texto. Com --voice, usa microfone e TTS local."""

    if voice:
        _voice_turn(heavy=heavy)
        return

    texto = " ".join(pergunta).strip()
    if not texto:
        click.echo(
            'Informe um pedido. Exemplo: yby ask "explica uma lista" '
            "(ou yby ask --voice / yby listen)",
            err=True,
        )
        raise SystemExit(1)

    resposta = build_engine().reply(texto, explicit_heavy=heavy)
    if resposta.notice:
        click.echo(resposta.notice, err=True)
    if resposta.provider == "none":
        raise SystemExit(1)

    motivo = "; ".join(resposta.reasons)
    click.echo(f"modelo: {resposta.provider} {resposta.model} ({motivo})", err=True)
    click.echo(resposta.text)


@cli.command("listen")
@click.option(
    "--heavy",
    is_flag=True,
    help="Força a nuvem, mesmo num pedido curto.",
)
def listen_cmd(heavy: bool) -> None:
    """Push-to-talk: grava até Enter, transcreve, pergunta e fala a resposta."""

    _voice_turn(heavy=heavy)


@cli.command("hub")
@click.option(
    "--once",
    is_flag=True,
    help="Uma checagem do Ollama e sai (sem loop).",
)
@click.option(
    "--interval",
    default=None,
    type=float,
    help="Segundos entre checagens (padrão: YBY_HUB_INTERVAL ou 60).",
)
def hub_cmd(once: bool, interval: float | None) -> None:
    """Keepalive do hub: pinga o Ollama em loop (serviço systemd)."""

    argv: list[str] = []
    if once:
        argv.append("--once")
    if interval is not None:
        argv.extend(["--interval", str(interval)])
    raise SystemExit(hub_main(argv))


@cli.command(
    context_settings={"ignore_unknown_options": True, "allow_interspersed_args": False},
)
@click.argument("comando", nargs=-1, required=True, type=click.UNPROCESSED)
def gate(comando: tuple[str, ...]) -> None:
    """Decide se um comando rodaria, pediria confirmação ou seria recusado.

    Não executa o comando.
    """

    texto = " ".join(comando).strip()
    policy = load_policy(default_policy_path())
    project_root = default_policy_path().parents[1]
    decision = decide(texto, policy=policy, project_root=project_root)
    click.echo(f"{decision.action}: {decision.reason}")
    if decision.action != "ask":
        raise SystemExit(0 if decision.action == "run" else 1)

    approved = confirm(
        texto,
        decision,
        input_fn=lambda: click.prompt("s/n", prompt_suffix=" "),
        output_fn=click.echo,
    )
    raise SystemExit(0 if approved else 1)


@cli.command()
@click.argument("titulo")
@click.argument("texto", nargs=-1, required=True)
def note(titulo: str, texto: tuple[str, ...]) -> None:
    """Grava uma nota Markdown no vault Obsidian."""

    load_dotenv(override=False)
    try:
        vault = vault_from_env()
        path = vault.write_note(titulo, " ".join(texto).strip() + "\n")
    except VaultError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    click.echo(path)


@cli.command("agent")
@click.argument("tarefa", nargs=-1, required=True)
@click.option(
    "--max-steps",
    default=8,
    show_default=True,
    type=click.IntRange(1, 32),
    help="Teto de iterações do loop.",
)
@click.option(
    "--script",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="JSON com lista de passos do planner (demo sem LLM).",
)
@click.option(
    "--local",
    is_flag=True,
    help="Planner via Ollama local (não usa nuvem neste comando).",
)
@click.option("--json", "as_json", is_flag=True, help="Saída estruturada em JSON.")
def agent_cmd(
    tarefa: tuple[str, ...],
    max_steps: int,
    script: Path | None,
    local: bool,
    as_json: bool,
) -> None:
    """Loop de agente controlado (P0). Fora do fluxo padrão do `ask`.

    Sem --script, use --local com Ollama. Tools: echo_json, vault_search (se YBY_VAULT_PATH).
    """

    load_dotenv(override=False)
    texto = " ".join(tarefa).strip()
    if not texto:
        click.echo('Informe uma tarefa. Exemplo: yby agent "resuma o vault"', err=True)
        raise SystemExit(1)
    if script and local:
        click.echo("Use apenas um de --script ou --local.", err=True)
        raise SystemExit(1)
    if not script and not local:
        click.echo(
            "Informe --script <arquivo.json> (demo) ou --local (Ollama).",
            err=True,
        )
        raise SystemExit(1)

    registry = vault_registry_or_skip()
    if script:
        raw = json.loads(script.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            click.echo("O script deve ser um JSON array de passos.", err=True)
            raise SystemExit(1)
        planner = ScriptedPlanner(raw)
    else:
        cfg = EngineConfig.from_env()
        planner = OllamaJsonPlanner(
            OllamaProvider(cfg.ollama_base_url, timeout=cfg.ollama_timeout),
            model=cfg.local_model,
        )

    loop = ControlledAgentLoop(
        registry=registry,
        planner=planner,
        max_iterations=max_steps,
    )
    result = loop.run(texto)

    if as_json:
        payload = {
            "status": result.status,
            "task": result.task,
            "iterations": result.iterations,
            "final_answer": result.final_answer,
            "abort_reason": result.abort_reason,
            "steps": [
                {
                    "iteration": s.iteration,
                    "kind": s.kind,
                    "detail": s.detail,
                    "error": s.error,
                }
                for s in result.steps
            ],
        }
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        click.echo(f"status: {result.status} ({result.iterations} passos)")
        if result.abort_reason:
            click.echo(f"abort: {result.abort_reason}", err=True)
        if result.final_answer is not None:
            click.echo(json.dumps(result.final_answer, ensure_ascii=False, indent=2))
        for step in result.steps:
            if step.error:
                click.echo(f"  [{step.kind}] erro: {step.error}", err=True)

    if result.status == "completed":
        raise SystemExit(0)
    if result.status == "aborted":
        raise SystemExit(2)
    raise SystemExit(1)


@cli.command()
@click.argument("consulta")
def recall(consulta: str) -> None:
    """Busca notas no índice do vault. Não chama a rede."""

    load_dotenv(override=False)
    try:
        hits = vault_from_env().search(consulta)
    except VaultError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    if not hits:
        click.echo("Nenhuma nota.")
        return
    for hit in hits:
        click.echo(f"{hit.score:.2f} {hit.name}")


def _confirm_cloud(message: str) -> bool:
    answer = click.prompt(message, default="n", show_default=False).strip().casefold()
    return answer in {"s", "sim", "y", "yes"}


def build_engine() -> HybridEngine:
    """Ponto de troca nos testes. Em execução normal, lê o ambiente."""

    return engine_from_env(
        confirm_fn=_confirm_cloud,
        has_tty_fn=lambda: sys.stdin.isatty() and sys.stdout.isatty(),
    )


def _wait_enter(_prompt: str = "") -> str:
    """Bloqueia até Enter no push-to-talk."""

    return click.get_text_stream("stdin").readline()


def _voice_turn(*, heavy: bool) -> None:
    """Fluxo de voz compartilhado por `ask --voice` e `listen`."""

    try:
        turn = listen_once(
            build_engine(),
            voice_config_from_env(),
            explicit_heavy=heavy,
            input_fn=_wait_enter,
            output_fn=lambda msg: click.echo(msg, err=True),
        )
    except VoiceError as exc:
        click.echo(str(exc), err=True)
        click.echo(
            "Texto continua disponível: python yby.py ask \"sua pergunta\"",
            err=True,
        )
        raise SystemExit(1) from exc

    resposta = turn.reply
    if resposta.notice:
        click.echo(resposta.notice, err=True)
    if resposta.provider == "none":
        raise SystemExit(1)

    motivo = "; ".join(resposta.reasons)
    click.echo(f"modelo: {resposta.provider} {resposta.model} ({motivo})", err=True)
    click.echo(resposta.text)


if __name__ == "__main__":
    cli()
