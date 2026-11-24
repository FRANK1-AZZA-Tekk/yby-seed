"""Orquestra coleta → avaliação → entrega (sem reparo)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.sentinel.clock import Clock, SystemClock
from src.sentinel.collectors import OllamaProbe, collect
from src.sentinel.config import SentinelConfig
from src.sentinel.evaluate import EvalAction, evaluate
from src.sentinel.models import ProbeSnapshot
from src.sentinel.notify import DesktopNotifier, Notifier
from src.sentinel.quiet import in_quiet_hours
from src.sentinel.store import (
    active_for_rule,
    load_incidents,
    load_runtime,
    save_incidents,
    save_runtime,
)


@dataclass
class TickResult:
    probe: ProbeSnapshot
    actions: list[EvalAction] = field(default_factory=list)
    notified: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    resolved: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def run_once(
    config: SentinelConfig,
    *,
    clock: Clock | None = None,
    notifier: Notifier | None = None,
    ollama_probe: OllamaProbe | None = None,
) -> TickResult:
    clk = clock or SystemClock()
    note = notifier or DesktopNotifier()
    now = clk.now()

    incidents = load_incidents(config.incidents_path)
    runtime = load_runtime(config.runtime_path)
    probe = collect(config, ollama_probe=ollama_probe, now=now)
    actions = evaluate(config, probe, runtime, incidents, now=now)

    result = TickResult(probe=probe, actions=list(actions))
    quiet = in_quiet_hours(now, config.quiet_hours)

    for action in actions:
        if action.kind == "open" and action.incident is not None:
            incidents.append(action.incident)
            result.notes.append(f"aberto {action.rule} id={action.incident.id}")
        elif action.kind == "resolve" and action.incident is not None:
            action.incident.state = "resolved"
            action.incident.resolved_at = now.timestamp()
            action.incident.pending_notify = False
            result.resolved.append(action.rule)
            result.notes.append(f"resolvido {action.rule}")

    # Entrega: incidentes ativos com pending_notify ou ainda sem notified_at
    for inc in incidents:
        if inc.state != "active":
            continue
        needs = inc.pending_notify or inc.notified_at is None
        if not needs:
            continue
        # Reavaliar condição antes de notificar (especialmente após quiet)
        if not _condition_still_failing(inc.rule, probe, config, now.timestamp(), runtime):
            inc.state = "resolved"
            inc.resolved_at = now.timestamp()
            inc.pending_notify = False
            result.resolved.append(inc.rule)
            result.notes.append(f"pré-notify: condição ok — resolve {inc.rule}")
            continue
        if quiet:
            inc.pending_notify = True
            result.pending.append(inc.rule)
            result.notes.append(f"horário silencioso — pendente {inc.rule}")
            continue
        rr = runtime.rule(inc.rule)
        if rr.paused:
            result.notes.append(f"pausada — sem notificar {inc.rule}")
            continue
        delivered = note.notify(f"YBY Sentinela: {inc.rule}", inc.message)
        if delivered:
            inc.notified_at = now.timestamp()
            inc.pending_notify = False
            result.notified.append(inc.rule)
            result.notes.append(f"notificado {inc.rule}")
        else:
            inc.pending_notify = True
            result.pending.append(inc.rule)
            result.notes.append(
                f"desktop indisponível — não marco entregue ({inc.rule})"
            )

    save_incidents(config.incidents_path, incidents)
    save_runtime(config.runtime_path, runtime)
    return result


def _condition_still_failing(
    rule: str,
    probe: ProbeSnapshot,
    config: SentinelConfig,
    now_ts: float,
    runtime: Any,
) -> bool:
    if rule == "ollama_down":
        if probe.ollama_ok:
            return False
        rr = runtime.rule(rule)
        if rr.fail_since is None:
            return False
        return (now_ts - rr.fail_since) >= config.ollama_down_seconds
    if rule == "vault_backup_stale":
        return probe.backup_status == "stale"
    if rule == "vault_backup_unverified":
        return probe.backup_status == "unverified"
    return False


def pause_rule(config: SentinelConfig, rule_id: str) -> bool:
    from src.sentinel.models import KNOWN_RULES

    if rule_id not in KNOWN_RULES:
        return False
    runtime = load_runtime(config.runtime_path)
    runtime.rule(rule_id).paused = True
    save_runtime(config.runtime_path, runtime)
    return True


def resume_rule(config: SentinelConfig, rule_id: str) -> bool:
    from src.sentinel.models import KNOWN_RULES

    if rule_id not in KNOWN_RULES:
        return False
    runtime = load_runtime(config.runtime_path)
    runtime.rule(rule_id).paused = False
    save_runtime(config.runtime_path, runtime)
    return True


def list_rules(config: SentinelConfig) -> list[dict[str, Any]]:
    from src.sentinel.models import KNOWN_RULES

    runtime = load_runtime(config.runtime_path)
    incidents = load_incidents(config.incidents_path)
    rows: list[dict[str, Any]] = []
    for rule_id in KNOWN_RULES:
        rr = runtime.rule(rule_id)
        active = active_for_rule(incidents, rule_id)
        rows.append(
            {
                "id": rule_id,
                "paused": rr.paused,
                "fail_since": rr.fail_since,
                "active_incident": None
                if active is None
                else {
                    "id": active.id,
                    "notified_at": active.notified_at,
                    "pending_notify": active.pending_notify,
                    "message": active.message,
                },
            }
        )
    return rows
