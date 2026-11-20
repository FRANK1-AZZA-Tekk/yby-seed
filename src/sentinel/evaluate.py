"""Avaliação de regras — puro em cima do snapshot + runtime."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from src.sentinel.config import SentinelConfig
from src.sentinel.models import Incident, KNOWN_RULES, ProbeSnapshot, SentinelRuntime
from src.sentinel.store import active_for_rule


@dataclass(frozen=True)
class EvalAction:
    """Efeito desejado sobre incidentes (ainda sem notificar)."""

    kind: str  # open | resolve | keep | skip_paused
    rule: str
    message: str = ""
    incident: Incident | None = None


def evaluate(
    config: SentinelConfig,
    probe: ProbeSnapshot,
    runtime: SentinelRuntime,
    incidents: list[Incident],
    *,
    now: datetime,
) -> list[EvalAction]:
    actions: list[EvalAction] = []
    ts = now.timestamp()

    # --- ollama_down ---
    actions.extend(
        _eval_duration_rule(
            rule="ollama_down",
            failing=not probe.ollama_ok,
            message=(
                f"Ollama indisponível há ≥{config.ollama_down_seconds:g}s "
                f"({probe.ollama_detail})"
            ),
            threshold_seconds=config.ollama_down_seconds,
            runtime=runtime,
            incidents=incidents,
            now_ts=ts,
        )
    )

    # --- backup stale vs unverified ---
    if probe.backup_status == "stale":
        actions.extend(
            _eval_immediate_rule(
                rule="vault_backup_stale",
                failing=True,
                message=probe.backup_detail,
                runtime=runtime,
                incidents=incidents,
                now_ts=ts,
            )
        )
        # recuperação implícita de unverified se estava ativo
        actions.extend(
            _eval_immediate_rule(
                rule="vault_backup_unverified",
                failing=False,
                message="",
                runtime=runtime,
                incidents=incidents,
                now_ts=ts,
            )
        )
    elif probe.backup_status == "unverified":
        actions.extend(
            _eval_immediate_rule(
                rule="vault_backup_unverified",
                failing=True,
                message=probe.backup_detail,
                runtime=runtime,
                incidents=incidents,
                now_ts=ts,
            )
        )
        actions.extend(
            _eval_immediate_rule(
                rule="vault_backup_stale",
                failing=False,
                message="",
                runtime=runtime,
                incidents=incidents,
                now_ts=ts,
            )
        )
    else:
        actions.extend(
            _eval_immediate_rule(
                rule="vault_backup_stale",
                failing=False,
                message="",
                runtime=runtime,
                incidents=incidents,
                now_ts=ts,
            )
        )
        actions.extend(
            _eval_immediate_rule(
                rule="vault_backup_unverified",
                failing=False,
                message="",
                runtime=runtime,
                incidents=incidents,
                now_ts=ts,
            )
        )

    return actions


def _eval_duration_rule(
    *,
    rule: str,
    failing: bool,
    message: str,
    threshold_seconds: float,
    runtime: SentinelRuntime,
    incidents: list[Incident],
    now_ts: float,
) -> list[EvalAction]:
    rr = runtime.rule(rule)
    active = active_for_rule(incidents, rule)
    if not failing:
        rr.fail_since = None
        if active is not None:
            return [EvalAction(kind="resolve", rule=rule, incident=active)]
        return [EvalAction(kind="keep", rule=rule)]

    if rr.paused:
        return [EvalAction(kind="skip_paused", rule=rule)]

    if rr.fail_since is None:
        rr.fail_since = now_ts
    duration = now_ts - rr.fail_since
    if duration < threshold_seconds:
        return [EvalAction(kind="keep", rule=rule)]

    if active is not None:
        return [EvalAction(kind="keep", rule=rule, incident=active, message=message)]

    incident = Incident(
        id=f"{rule}-{uuid.uuid4().hex[:10]}",
        rule=rule,
        state="active",
        message=message,
        opened_at=now_ts,
        pending_notify=True,
    )
    return [EvalAction(kind="open", rule=rule, message=message, incident=incident)]


def _eval_immediate_rule(
    *,
    rule: str,
    failing: bool,
    message: str,
    runtime: SentinelRuntime,
    incidents: list[Incident],
    now_ts: float,
) -> list[EvalAction]:
    rr = runtime.rule(rule)
    active = active_for_rule(incidents, rule)
    if not failing:
        rr.fail_since = None
        if active is not None:
            return [EvalAction(kind="resolve", rule=rule, incident=active)]
        return [EvalAction(kind="keep", rule=rule)]

    if rr.paused:
        return [EvalAction(kind="skip_paused", rule=rule)]

    if rr.fail_since is None:
        rr.fail_since = now_ts

    if active is not None:
        return [EvalAction(kind="keep", rule=rule, incident=active, message=message)]

    incident = Incident(
        id=f"{rule}-{uuid.uuid4().hex[:10]}",
        rule=rule,
        state="active",
        message=message or f"regra {rule}",
        opened_at=now_ts,
        pending_notify=True,
    )
    return [EvalAction(kind="open", rule=rule, message=message, incident=incident)]


def list_rule_ids() -> list[str]:
    return list(KNOWN_RULES)
