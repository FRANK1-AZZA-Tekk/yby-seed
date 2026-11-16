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
    backup  - Backup local do vault + logs redigidos (sem nuvem)
    usage   - Resumo/tail do cloud_usage.jsonl + orçamento mensal
    learn   - Aprendizado diário (JSONL + relatório; sem auto-merge)
    brief   - Entrevista YBY-BRIEF (sem gerar código/plano)
    plan    - Plano verificável a partir de brief (não executa)
    cursor-fake - Dry-run de plano validated (sem MCP / sem escrita)
    scaffold - Propõe/aplica artefatos Python CLI (sem install)
    agent   - Loop de agente P0 (opt-in; não altera o ask)
"""

import json
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from loguru import logger

from src.actions.limits import DEFAULT_TIMEOUT, RunnerLimitError, normalize_timeout
from src.actions.runner import run_command
from src.agent_loop.loop import ControlledAgentLoop
from src.agent_loop.planner import OllamaJsonPlanner, ScriptedPlanner
from src.agent_loop.tools import vault_registry_or_skip
from src.artifacts.generator import (
    ArtifactError,
    apply_manifest,
    propose_scaffold,
    revert_applied,
    run_generated_tests,
)
from src.artifacts.validate import format_report, validate_contents
from src.backup.local import (
    BackupError,
    backup_dir_from_env,
    create_backup,
    keep_from_env,
    list_backups,
    restore_backup,
)
from src.brief.interview import (
    BriefError,
    answer_field,
    format_status,
    start_brief,
    try_propose,
)
from src.brief.schemas import BRIEF_FIELDS
from src.brief.store import load_or_create_store
from src.conversation.explain import (
    format_cli_error,
    format_command_decision,
    format_engine_reply,
    format_vague_ask,
    is_vague_request,
)
from src.cursor_fake.adapter import (
    CursorFakeError,
    format_report as format_cursor_fake_report,
    simulate as cursor_fake_simulate,
)
from src.engine.budget import CloudBudget, CloudBudgetError
from src.engine.cloud_usage_log import CloudUsageLog
from src.engine.config import EngineConfig
from src.engine.hybrid import HybridEngine, engine_from_env
from src.engine.providers import OllamaProvider
from src.learn.daily import (
    LEARN_KINDS,
    LearnError,
    append_entry,
    format_report as format_learn_report,
    learn_log_path_from_env,
    report_for_day,
)
from src.memory.vault import VaultError, vault_from_env
from src.obs.usage import (
    UsageError,
    format_events,
    format_summary,
    read_events,
    summarize,
)
from src.plan.builder import PlanError, build_plan_from_brief, revise_plan
from src.plan.schemas import PlanStep
from src.plan.store import load_or_create_plan_store
from src.plan.validate import validate_plan
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

    try:
        effective_timeout = normalize_timeout(timeout)
    except RunnerLimitError as exc:
        click.echo(
            format_cli_error(
                kind="run",
                detail=str(exc),
                next_step="use --timeout entre 0.1s e YBY_RUN_TIMEOUT_MAX (padrão 120)",
            ),
            err=True,
        )
        raise SystemExit(1) from exc

    policy = load_policy(default_policy_path())
    project_root = default_policy_path().parents[1]
    result = run_command(
        texto,
        policy=policy,
        project_root=project_root,
        timeout=effective_timeout,
        input_fn=lambda: click.prompt("s/n", prompt_suffix=" "),
        output_fn=click.echo,
    )

    if not result.approved:
        click.echo(format_command_decision(texto, result.decision), err=True)
        raise SystemExit(1)

    if result.approved and not result.executed and result.stderr:
        click.echo(
            format_cli_error(
                kind="run",
                detail=result.stderr,
                next_step="não execute código de scaffold aplicado; sem sandbox OS no v1",
            ),
            err=True,
        )
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
        click.echo(f"timeout após {effective_timeout:g}s", err=True)
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


@cli.group("cursor-fake")
def cursor_fake_grp() -> None:
    """Adaptador Cursor fake: dry-run de plano validated (sem MCP)."""


@cursor_fake_grp.command("simulate")
@click.argument("plan_id")
@click.option(
    "--dir",
    "plan_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Pasta dos planos (padrão: vault/.yby/plans ou .yby/plans).",
)
@click.option("--json", "as_json", is_flag=True, help="Saída estruturada em JSON.")
def cursor_fake_simulate_cmd(
    plan_id: str, plan_dir: Path | None, as_json: bool
) -> None:
    """Simula execução do plano sem escrever disco nem chamar MCP."""

    load_dotenv(override=False)
    try:
        plan = load_or_create_plan_store(plan_dir).load(plan_id)
        report = cursor_fake_simulate(plan)
    except FileNotFoundError as exc:
        click.echo(
            format_cli_error(
                kind="cursor-fake",
                detail=str(exc),
                next_step="gere um plano com yby plan from-brief <brief_id>",
            ),
            err=True,
        )
        raise SystemExit(1) from exc
    except CursorFakeError as exc:
        click.echo(
            format_cli_error(
                kind="cursor-fake",
                detail=str(exc),
                next_step="use um plano status=validated",
            ),
            err=True,
        )
        raise SystemExit(1) from exc
    if as_json:
        click.echo(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
    else:
        click.echo(format_cursor_fake_report(report))


@cli.group()
def scaffold() -> None:
    """Gerador de artefatos (Python CLI). Sem pip install / deploy."""


@scaffold.command("propose")
@click.argument("plan_id")
@click.argument("target", type=click.Path(file_okay=False, path_type=Path))
@click.option("--name", required=True, help="Nome do pacote Python.")
@click.option("--objective", default="scaffold local YBY", show_default=True)
@click.option(
    "--plan-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Salva manifesto JSON da proposta.",
)
def scaffold_propose(
    plan_id: str,
    target: Path,
    name: str,
    objective: str,
    plan_dir: Path | None,
    out: Path | None,
) -> None:
    """Propõe scaffold em memória/manifesto. Não escreve o projeto ainda."""

    load_dotenv(override=False)
    try:
        plan = load_or_create_plan_store(plan_dir).load(plan_id)
        manifest, contents = propose_scaffold(
            plan, target, name=name, objective=objective
        )
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    except ArtifactError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    payload = {
        "manifest": manifest.model_dump(),
        "files": sorted(contents),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        # stash contents next to manifest for apply
        stash = out.with_suffix(".contents.json")
        stash.write_text(
            json.dumps(contents, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        click.echo(f"proposta: {out}")
        click.echo(f"conteudos: {stash}")
    click.echo(text)


@scaffold.command("apply")
@click.argument("proposal", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--approve-overwrite",
    is_flag=True,
    help="Permite substituir arquivo existente (default: recusa).",
)
def scaffold_apply(proposal: Path, approve_overwrite: bool) -> None:
    """Aplica proposta salva por `scaffold propose --out`."""

    payload = json.loads(proposal.read_text(encoding="utf-8"))
    from src.artifacts.manifest import ArtifactManifest

    try:
        manifest = ArtifactManifest.model_validate(payload["manifest"])
        stash = proposal.with_suffix(".contents.json")
        if not stash.is_file():
            raise ArtifactError(f"faltam conteúdos: {stash}")
        contents = json.loads(stash.read_text(encoding="utf-8"))
        applied = apply_manifest(
            manifest, contents, approve_overwrite=approve_overwrite
        )
    except (ArtifactError, KeyError, json.JSONDecodeError) as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    click.echo(f"applied: {applied.target_dir}")
    click.echo(json.dumps(applied.model_dump(), ensure_ascii=False, indent=2))


@scaffold.command("revert")
@click.argument("target", type=click.Path(exists=True, file_okay=False, path_type=Path))
def scaffold_revert(target: Path) -> None:
    """Remove arquivos do manifesto aplicado no alvo."""

    from src.artifacts.manifest import ArtifactManifest

    man = target / ".yby" / "artifacts-manifest.json"
    if not man.is_file():
        click.echo("manifesto não encontrado", err=True)
        raise SystemExit(1)
    try:
        manifest = ArtifactManifest.model_validate_json(man.read_text(encoding="utf-8"))
        reverted = revert_applied(manifest)
    except ArtifactError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    click.echo(f"status: {reverted.status}")


@scaffold.command("validate")
@click.argument("proposal", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def scaffold_validate(proposal: Path) -> None:
    """Validação estática da proposta. Não executa código gerado."""

    try:
        json.loads(proposal.read_text(encoding="utf-8"))
        stash = proposal.with_suffix(".contents.json")
        contents = json.loads(stash.read_text(encoding="utf-8"))
        if not isinstance(contents, dict):
            raise ArtifactError("conteúdos inválidos")
        report = validate_contents(contents)
        click.echo(format_report(report))
        if not report.ok:
            raise SystemExit(1)
    except (OSError, json.JSONDecodeError, KeyError, ArtifactError) as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc


@scaffold.command("test-generated")
@click.argument("target", type=click.Path(exists=True, file_okay=False, path_type=Path))
def scaffold_test_generated(target: Path) -> None:
    """Bloqueado: sem sandbox OS não executamos código gerado."""

    try:
        run_generated_tests(target)
    except ArtifactError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc


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


@cli.group()
def backup() -> None:
    """Backup local do vault + logs redigidos (sem nuvem)."""


@backup.command("create")
@click.option(
    "--dir",
    "backup_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Pasta de archives (padrão: YBY_BACKUP_DIR ou backups/yby).",
)
@click.option(
    "--keep",
    type=int,
    default=None,
    help="Quantos archives manter (padrão: YBY_BACKUP_KEEP ou 7).",
)
def backup_create(backup_dir: Path | None, keep: int | None) -> None:
    """Cria tar.gz com vault e logs redigidos; aplica retenção."""

    load_dotenv(override=False)
    try:
        vault = vault_from_env()
        dest = backup_dir or backup_dir_from_env()
        retention = keep if keep is not None else keep_from_env()
        log_path = CloudUsageLog.from_env().path
        info = create_backup(
            vault_path=vault.root,
            backup_dir=dest,
            log_paths=[log_path],
            keep=retention,
        )
    except (VaultError, BackupError) as exc:
        click.echo(
            format_cli_error(
                kind="backup",
                detail=str(exc),
                next_step="confira YBY_VAULT_PATH / YBY_BACKUP_DIR e tente de novo",
            ),
            err=True,
        )
        raise SystemExit(1) from exc
    click.echo(f"{info.path} ({info.size_bytes} bytes)")


@backup.command("list")
@click.option(
    "--dir",
    "backup_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Pasta de archives (padrão: YBY_BACKUP_DIR ou backups/yby).",
)
def backup_list(backup_dir: Path | None) -> None:
    """Lista archives locais (mais recente primeiro)."""

    load_dotenv(override=False)
    try:
        dest = backup_dir or backup_dir_from_env()
        items = list_backups(dest)
    except BackupError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    if not items:
        click.echo("(nenhum backup)")
        return
    for info in items:
        click.echo(f"{info.stamp}\t{info.size_bytes}\t{info.path}")


@backup.command("restore")
@click.argument("archive", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("target", type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "--force",
    is_flag=True,
    help="Permite restaurar em pasta não vazia (ainda não aponta ao vault ativo).",
)
def backup_restore(archive: Path, target: Path, force: bool) -> None:
    """Restaura vault do archive para um diretório alvo (não sobrescreve o vault ativo)."""

    load_dotenv(override=False)
    try:
        restored = restore_backup(archive, target, force=force)
    except BackupError as exc:
        click.echo(
            format_cli_error(
                kind="backup",
                detail=str(exc),
                next_step="use um alvo vazio ou --force; nunca aponte ao vault vivo sem copiar antes",
            ),
            err=True,
        )
        raise SystemExit(1) from exc
    click.echo(restored)


@cli.group(invoke_without_command=True)
@click.pass_context
def usage(ctx: click.Context) -> None:
    """Resumo do cloud_usage.jsonl e orçamento mensal (local; sem Datadog)."""

    if ctx.invoked_subcommand is None:
        ctx.invoke(usage_summary)


@usage.command("summary")
def usage_summary() -> None:
    """Mostra modo, tokens do mês UTC e contagem por resultado."""

    load_dotenv(override=False)
    try:
        log = CloudUsageLog.from_env()
        budget = CloudBudget.from_env()
        report = summarize(log_path=log.path, budget=budget)
    except (UsageError, CloudBudgetError) as exc:
        click.echo(
            format_cli_error(
                kind="usage",
                detail=str(exc),
                next_step="confira YBY_CLOUD_LOG_PATH / YBY_CLOUD_MODE",
            ),
            err=True,
        )
        raise SystemExit(1) from exc
    click.echo(format_summary(report))


@usage.command("tail")
@click.option(
    "--limit",
    default=20,
    show_default=True,
    type=click.IntRange(1, 500),
    help="Quantos eventos mais recentes mostrar.",
)
def usage_tail(limit: int) -> None:
    """Lista os últimos eventos do JSONL (metadados apenas)."""

    load_dotenv(override=False)
    try:
        log = CloudUsageLog.from_env()
        events = read_events(log.path)
        click.echo(format_events(events, limit=limit))
    except UsageError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc


@cli.group()
def learn() -> None:
    """Aprendizado diário (JSONL + relatório). Sem auto-merge em docs."""


@learn.command("log")
@click.argument("kind")
@click.argument("summary", nargs=-1, required=True)
@click.option(
    "--tag",
    "tags",
    multiple=True,
    help="Tag opcional (repetível).",
)
@click.option(
    "--log-path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="JSONL (padrão: YBY_LEARN_LOG_PATH ou logs/learn.jsonl).",
)
def learn_log(kind: str, summary: tuple[str, ...], tags: tuple[str, ...], log_path: Path | None) -> None:
    """Registra um aprendizado (success|failure|note|insight)."""

    load_dotenv(override=False)
    try:
        path = log_path or learn_log_path_from_env()
        entry = append_entry(
            kind=kind,
            summary=" ".join(summary).strip(),
            log_path=path,
            tags=list(tags),
        )
    except LearnError as exc:
        click.echo(
            format_cli_error(
                kind="learn",
                detail=str(exc),
                next_step=f"use kind em {{{', '.join(sorted(LEARN_KINDS))}}} sem segredos",
            ),
            err=True,
        )
        raise SystemExit(1) from exc
    click.echo(f"{entry.day}\t{entry.kind}\t{entry.summary}")


@learn.command("report")
@click.option(
    "--day",
    default=None,
    help="Dia UTC YYYY-MM-DD (padrão: hoje).",
)
@click.option(
    "--log-path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="JSONL (padrão: YBY_LEARN_LOG_PATH ou logs/learn.jsonl).",
)
@click.option("--json", "as_json", is_flag=True, help="Saída estruturada em JSON.")
def learn_report(day: str | None, log_path: Path | None, as_json: bool) -> None:
    """Mostra relatório do dia. Não grava em docs/LEARNING.md."""

    load_dotenv(override=False)
    try:
        path = log_path or learn_log_path_from_env()
        report = report_for_day(log_path=path, day=day)
    except LearnError as exc:
        click.echo(
            format_cli_error(
                kind="learn",
                detail=str(exc),
                next_step="use --day YYYY-MM-DD e confira YBY_LEARN_LOG_PATH",
            ),
            err=True,
        )
        raise SystemExit(1) from exc
    if as_json:
        payload = {
            "day": report.day,
            "log_path": str(report.log_path),
            "total": report.total,
            "by_kind": report.by_kind,
            "note": report.note,
            "entries": [
                {
                    "timestamp": e.timestamp,
                    "day": e.day,
                    "kind": e.kind,
                    "summary": e.summary,
                    "source": e.source,
                    "tags": list(e.tags),
                }
                for e in report.entries
            ],
        }
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        click.echo(format_learn_report(report))


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
