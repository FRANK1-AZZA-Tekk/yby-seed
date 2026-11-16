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
    ask     - Responde em texto (sem shell); --explain = envelope professor;
              --voice grava, pergunta e fala
    listen  - Push-to-talk: grava até Enter → ask → TTS
    hub     - Keepalive do PC Hub (saúde do Ollama)
    run     - Executa comando após a porta de segurança
    gate    - Só decide (com envelope); não executa
    note    - Grava nota no vault
    recall  - Busca no vault
    brief   - Entrevista YBY-BRIEF (sem gerar código/plano)
    plan    - Plano verificável a partir de brief (não executa)
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
from src.brief.interview import (
    BriefError,
    answer_field,
    format_status,
    start_brief,
    try_propose,
)
from src.brief.schemas import BRIEF_FIELDS
from src.brief.store import load_or_create_store
from src.plan.builder import PlanError, build_plan_from_brief, revise_plan
from src.plan.schemas import PlanStep
from src.plan.store import load_or_create_plan_store
from src.plan.validate import validate_plan
from src.conversation.explain import (
    format_cli_error,
    format_command_decision,
    format_engine_reply,
    format_vague_ask,
    is_vague_request,
)
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
        click.echo(format_command_decision(texto, result.decision), err=True)
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
@click.option(
    "--explain",
    is_flag=True,
    help="Modo professor: envelope Entendi/Falta/Proposta/Risco/Próximo passo.",
)
@click.argument("pergunta", nargs=-1, required=False)
def ask(heavy: bool, voice: bool, explain: bool, pergunta: tuple[str, ...]) -> None:
    """Responde um pedido em texto. Com --voice, usa microfone e TTS local."""

    if voice:
        _voice_turn(heavy=heavy)
        return

    texto = " ".join(pergunta).strip()
    if not texto:
        click.echo(
            'Informe um pedido. Exemplo: yby ask "explica uma lista" '
            "(ou yby ask --voice / yby listen / yby ask --explain \"...\")",
            err=True,
        )
        raise SystemExit(1)

    if explain and is_vague_request(texto):
        click.echo(format_vague_ask(texto))
        raise SystemExit(0)

    resposta = build_engine().reply(texto, explicit_heavy=heavy)
    if resposta.notice and not explain:
        click.echo(resposta.notice, err=True)
    if resposta.provider == "none":
        if explain:
            click.echo(
                format_engine_reply(
                    prompt=texto,
                    text=resposta.text or "(sem resposta)",
                    provider=resposta.provider or "none",
                    model=resposta.model or "-",
                    reasons=resposta.reasons,
                    notice=resposta.notice,
                )
            )
        raise SystemExit(1)

    if explain:
        click.echo(
            format_engine_reply(
                prompt=texto,
                text=resposta.text,
                provider=resposta.provider,
                model=resposta.model,
                reasons=resposta.reasons,
                notice=resposta.notice,
            )
        )
        return

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
    click.echo(format_command_decision(texto, decision))
    if decision.action != "ask":
        raise SystemExit(0 if decision.action == "run" else 1)

    approved = confirm(
        texto,
        decision,
        input_fn=lambda: click.prompt("s/n", prompt_suffix=" "),
        output_fn=click.echo,
    )
    raise SystemExit(0 if approved else 1)


@cli.group()
def brief() -> None:
    """Entrevista YBY-BRIEF: ideia → campos → proposta (não executa, não gera código)."""


@brief.command("start")
@click.argument("ideia", nargs=-1, required=True)
@click.option(
    "--dir",
    "store_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Pasta de briefs (default: YBY_VAULT_PATH/.yby/briefs ou ./.yby/briefs).",
)
def brief_start(ideia: tuple[str, ...], store_dir: Path | None) -> None:
    """Inicia um brief a partir de uma ideia em linguagem natural."""

    load_dotenv(override=False)
    try:
        draft, questions = start_brief(" ".join(ideia))
        path = load_or_create_store(store_dir).save(draft)
    except BriefError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    click.echo(f"id: {draft.id}")
    click.echo(f"salvo: {path}")
    click.echo(format_status(draft))
    if questions:
        click.echo("perguntas:")
        for index, question in enumerate(questions, start=1):
            click.echo(f"  {index}. {question}")


@brief.command("answer")
@click.argument("brief_id")
@click.argument("campo")
@click.argument("texto", nargs=-1, required=True)
@click.option(
    "--dir",
    "store_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
def brief_answer(
    brief_id: str, campo: str, texto: tuple[str, ...], store_dir: Path | None
) -> None:
    """Responde um campo (retomada). Campos: objective, audience, scope, …"""

    load_dotenv(override=False)
    store = load_or_create_store(store_dir)
    try:
        draft = store.load(brief_id)
        answer_field(draft, campo, " ".join(texto))
        store.save(draft)
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    except BriefError as exc:
        click.echo(str(exc), err=True)
        known = ", ".join(key for key, _ in BRIEF_FIELDS)
        click.echo(f"campos: {known}", err=True)
        raise SystemExit(1) from exc
    click.echo(format_status(draft))


@brief.command("show")
@click.argument("brief_id")
@click.option(
    "--dir",
    "store_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--cloud-safe",
    is_flag=True,
    help="JSON sem segredos (omite campos marcados sensíveis).",
)
def brief_show(brief_id: str, store_dir: Path | None, cloud_safe: bool) -> None:
    """Mostra o brief (retomada)."""

    load_dotenv(override=False)
    try:
        draft = load_or_create_store(store_dir).load(brief_id)
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    if cloud_safe:
        click.echo(json.dumps(draft.cloud_safe_dict(), ensure_ascii=False, indent=2))
        return
    click.echo(format_status(draft))
    click.echo(json.dumps(draft.model_dump(), ensure_ascii=False, indent=2))


@brief.command("propose")
@click.argument("brief_id")
@click.option(
    "--dir",
    "store_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
def brief_propose(brief_id: str, store_dir: Path | None) -> None:
    """Gera proposta só se o brief estiver completo. Não gera plano nem código."""

    load_dotenv(override=False)
    store = load_or_create_store(store_dir)
    try:
        draft = store.load(brief_id)
        proposal = try_propose(draft)
        store.save(draft)
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    except BriefError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    click.echo(proposal)


@cli.group("plan")
def plan_grp() -> None:
    """Plano verificável (YBY-PLAN). Não executa etapas."""


@plan_grp.command("from-brief")
@click.argument("brief_id")
@click.option(
    "--brief-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--dir",
    "plan_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
def plan_from_brief(brief_id: str, brief_dir: Path | None, plan_dir: Path | None) -> None:
    """Gera plano validado a partir de um brief completo."""

    load_dotenv(override=False)
    try:
        brief = load_or_create_store(brief_dir).load(brief_id)
        plan = build_plan_from_brief(brief)
        path = load_or_create_plan_store(plan_dir).save(plan)
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    except PlanError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    click.echo(f"id: {plan.id}")
    click.echo(f"version: {plan.version}")
    click.echo(f"status: {plan.status}")
    click.echo(f"salvo: {path}")
    click.echo(json.dumps(plan.model_dump(), ensure_ascii=False, indent=2))


@plan_grp.command("show")
@click.argument("plan_id")
@click.option("--version", type=int, default=None)
@click.option(
    "--dir",
    "plan_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
def plan_show(plan_id: str, version: int | None, plan_dir: Path | None) -> None:
    """Mostra um plano (opcionalmente uma versão)."""

    load_dotenv(override=False)
    try:
        plan = load_or_create_plan_store(plan_dir).load(plan_id, version=version)
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    click.echo(json.dumps(plan.model_dump(), ensure_ascii=False, indent=2))


@plan_grp.command("validate")
@click.argument("plan_id")
@click.argument("brief_id")
@click.option(
    "--dir",
    "plan_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--brief-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
def plan_validate(
    plan_id: str, brief_id: str, plan_dir: Path | None, brief_dir: Path | None
) -> None:
    """Revalida plano vs brief e allowlist (sem executar)."""

    load_dotenv(override=False)
    try:
        plan = load_or_create_plan_store(plan_dir).load(plan_id)
        brief = load_or_create_store(brief_dir).load(brief_id)
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    reasons = validate_plan(plan, brief)
    if reasons:
        for reason in reasons:
            click.echo(reason, err=True)
        raise SystemExit(1)
    click.echo("ok")


@plan_grp.command("revise")
@click.argument("plan_id")
@click.argument("brief_id")
@click.option(
    "--dir",
    "plan_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--brief-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--drop-step",
    multiple=True,
    help="Remove etapa por id e grava nova versão.",
)
def plan_revise(
    plan_id: str,
    brief_id: str,
    plan_dir: Path | None,
    brief_dir: Path | None,
    drop_step: tuple[str, ...],
) -> None:
    """Nova versão do plano (ex.: remove etapas). Não executa."""

    load_dotenv(override=False)
    store = load_or_create_plan_store(plan_dir)
    try:
        plan = store.load(plan_id)
        brief = load_or_create_store(brief_dir).load(brief_id)
        steps: list[PlanStep] | None = None
        if drop_step:
            drop = set(drop_step)
            steps = [s for s in plan.steps if s.id not in drop]
        updated = revise_plan(plan, brief, steps=steps)
        path = store.save(updated)
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    except PlanError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    click.echo(f"id: {updated.id}")
    click.echo(f"version: {updated.version}")
    click.echo(f"salvo: {path}")


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
        click.echo(
            format_cli_error(
                kind="vault",
                detail=str(exc),
                next_step="defina YBY_VAULT_PATH para uma pasta gravável e tente de novo",
            ),
            err=True,
        )
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
        click.echo(
            format_cli_error(
                kind="vault",
                detail=str(exc),
                next_step="defina YBY_VAULT_PATH e rode yby note antes de recall",
            ),
            err=True,
        )
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
