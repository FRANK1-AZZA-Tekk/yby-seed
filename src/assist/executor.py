"""Executor único: validate → policy → tool (sem anunciar sucesso antecipado)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.assist.audit import append_audit
from src.assist.capabilities import validate_tool_args
from src.assist.config import AssistConfig
from src.assist.policy import decide_policy
from src.assist.reminders import Clock, ReminderStore
from src.assist.tools import (
    Launcher,
    tool_app_open,
    tool_chat,
    tool_clarify,
    tool_files_find,
    tool_reminder_create_confirmed,
    tool_sentinel_rules_list,
    tool_sentinel_rules_pause,
    tool_sentinel_rules_resume,
    tool_system_status,
    tool_vault_search,
)
from src.assist.types import PolicyDecision, ToolProposal, ToolResult
from src.memory.vault import Vault


ConfirmFn = Callable[[str], bool]


def execute_proposal(
    config: AssistConfig,
    proposal: ToolProposal,
    *,
    confirm_fn: ConfirmFn | None = None,
    launcher: Launcher | None = None,
    vault: Vault | None = None,
    reminder_store: ReminderStore | None = None,
    clock: Clock | None = None,
    pending_reminder: dict[str, Any] | None = None,
    set_pending_reminder: Callable[[dict[str, Any] | None], None] | None = None,
    _routine_depth: int = 0,
) -> tuple[PolicyDecision, ToolResult]:
    """Executa uma proposta já estruturada. Rotinas não aninham rotinas."""

    try:
        validate_tool_args(proposal.tool, proposal.args)
    except (KeyError, ValueError) as exc:
        decision = PolicyDecision("refuse", str(exc))
        result = ToolResult(
            ok=False,
            tool=proposal.tool,
            error=str(exc),
            narration=f"Não executei nada: {exc}",
        )
        _audit(config, result)
        return decision, result

    decision = decide_policy(config, proposal)
    if decision.action == "refuse":
        result = ToolResult(
            ok=False,
            tool=proposal.tool,
            error=decision.reason,
            narration=f"Recusado pela política: {decision.reason}",
        )
        _audit(config, result)
        return decision, result

    if proposal.tool == "reminder.create":
        return _handle_reminder(
            config,
            proposal,
            decision,
            confirm_fn=confirm_fn,
            reminder_store=reminder_store,
            set_pending_reminder=set_pending_reminder,
        )

    if decision.action == "confirm":
        preview = _preview(proposal)
        if confirm_fn is None or not confirm_fn(preview):
            result = ToolResult(
                ok=False,
                tool=proposal.tool,
                error="confirmação negada ou indisponível",
                narration="Não executei: confirmação não concedida.",
            )
            _audit(config, result)
            return decision, result

    if proposal.tool == "routine.run":
        if _routine_depth > 0:
            result = ToolResult(
                ok=False,
                tool="routine.run",
                error="rotina aninhada proibida",
                narration="Rotinas não podem chamar outras rotinas neste PR.",
            )
            _audit(config, result)
            return decision, result
        result = _run_routine(
            config,
            str(proposal.args.get("name", "")),
            confirm_fn=confirm_fn,
            launcher=launcher,
            vault=vault,
            reminder_store=reminder_store,
            clock=clock,
            set_pending_reminder=set_pending_reminder,
        )
        _audit(config, result)
        return decision, result

    result = _dispatch(
        config,
        proposal,
        launcher=launcher,
        vault=vault,
        reminder_store=reminder_store,
    )
    _audit(config, result)
    return decision, result


def _handle_reminder(
    config: AssistConfig,
    proposal: ToolProposal,
    decision: PolicyDecision,
    *,
    confirm_fn: ConfirmFn | None,
    reminder_store: ReminderStore | None,
    set_pending_reminder: Callable[[dict[str, Any] | None], None] | None,
) -> tuple[PolicyDecision, ToolResult]:
    args = {
        "text": str(proposal.args.get("text", "")),
        "date": str(proposal.args.get("date", "")),
        "time": str(proposal.args.get("time", "")),
        "tz": str(proposal.args.get("tz") or "America/Sao_Paulo"),
    }
    preview = (
        f"Confirmar lembrete?\n"
        f"  texto: {args['text']}\n"
        f"  data: {args['date']}\n"
        f"  hora: {args['time']}\n"
        f"  fuso: {args['tz']}\n"
        f"[s/n] (cancela descarta)"
    )
    if set_pending_reminder is not None:
        set_pending_reminder(dict(args))
    if confirm_fn is None or not confirm_fn(preview):
        if set_pending_reminder is not None:
            set_pending_reminder(None)
        result = ToolResult(
            ok=False,
            tool="reminder.create",
            error="confirmação negada",
            narration="Lembrete não salvo (confirmação negada ou cancelada).",
        )
        _audit(config, result)
        return decision, result

    store = reminder_store or ReminderStore(config.reminders_path)
    result = tool_reminder_create_confirmed(
        store,
        text=args["text"],
        date=args["date"],
        time=args["time"],
        tz=args["tz"],
    )
    if set_pending_reminder is not None:
        set_pending_reminder(None)
    _audit(config, result)
    return decision, result


def _run_routine(
    config: AssistConfig,
    name: str,
    **kwargs: Any,
) -> ToolResult:
    key = name.strip().casefold()
    entry = config.routines.get(key)
    if entry is None:
        return ToolResult(
            ok=False,
            tool="routine.run",
            error=f"rotina não cadastrada: {name}",
            narration=f"Rotina '{name}' não existe na configuração.",
        )
    ran: list[str] = []
    skipped: list[str] = []
    failed: str | None = None
    steps = list(entry.steps)
    for idx, step in enumerate(steps):
        if step.tool == "routine.run":
            failed = "passo tenta rotina aninhada"
            skipped = [s.tool for s in steps[idx + 1 :]]
            break
        prop = ToolProposal(tool=step.tool, args=dict(step.args), source="alias")
        _decision, result = execute_proposal(
            config,
            prop,
            _routine_depth=1,
            **kwargs,
        )
        if not result.ok:
            failed = f"{step.tool}: {result.error or result.narration}"
            skipped = [s.tool for s in steps[idx + 1 :]]
            break
        ran.append(step.tool)
    ok = failed is None
    narration = (
        f"Rotina '{key}' concluída ({len(ran)} passo(s))."
        if ok
        else (
            f"Rotina '{key}' interrompida. "
            f"Rodou: {ran or '[]'}. Falhou: {failed}. "
            f"Não rodou: {skipped or '[]'}."
        )
    )
    return ToolResult(
        ok=ok,
        tool="routine.run",
        data={"name": key, "ran": ran, "failed": failed, "skipped": skipped},
        error=failed,
        narration=narration,
    )


def _dispatch(
    config: AssistConfig,
    proposal: ToolProposal,
    *,
    launcher: Launcher | None,
    vault: Vault | None,
    reminder_store: ReminderStore | None,
) -> ToolResult:
    tool = proposal.tool
    args = proposal.args
    if tool == "app.open":
        return tool_app_open(config, name=str(args.get("name", "")), launcher=launcher)
    if tool == "files.find":
        limit = int(args.get("limit") or config.find_limit_default)
        return tool_files_find(config, query=str(args.get("query", "")), limit=limit)
    if tool == "vault.search":
        return tool_vault_search(
            query=str(args.get("query", "")),
            k=int(args.get("k") or 3),
            vault=vault,
        )
    if tool == "system.status":
        return tool_system_status(config)
    if tool == "clarify":
        return tool_clarify(question=str(args.get("question", "")))
    if tool == "chat":
        return tool_chat(text=str(args.get("text", "")))
    if tool == "sentinel.rules.list":
        return tool_sentinel_rules_list()
    if tool == "sentinel.rules.pause":
        return tool_sentinel_rules_pause(rule=str(args.get("rule", "")))
    if tool == "sentinel.rules.resume":
        return tool_sentinel_rules_resume(rule=str(args.get("rule", "")))
    return ToolResult(
        ok=False,
        tool=tool,
        error="handler ausente",
        narration=f"Ferramenta '{tool}' sem handler.",
    )


def _preview(proposal: ToolProposal) -> str:
    return f"Confirmar {proposal.tool} com args={proposal.args}? [s/n]"


def _audit(config: AssistConfig, result: ToolResult) -> None:
    try:
        meta: dict[str, object] = {"keys": sorted(result.data.keys())}
        if result.tool == "routine.run":
            for key in ("ran", "failed", "skipped", "name"):
                if key in result.data:
                    meta[key] = result.data[key]
        append_audit(
            config.audit_log_path,
            tool=result.tool,
            ok=result.ok,
            error=result.error,
            meta=meta,
        )
    except OSError:
        pass
