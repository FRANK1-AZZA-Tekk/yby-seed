"""Modelos do Sentinela (contrato painel + runtime)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

RuleId = Literal["ollama_down", "vault_backup_stale", "vault_backup_unverified"]
IncidentState = Literal["active", "resolved"]

KNOWN_RULES: tuple[str, ...] = (
    "ollama_down",
    "vault_backup_stale",
    "vault_backup_unverified",
)


@dataclass
class Incident:
    id: str
    rule: str
    state: IncidentState
    message: str
    notified_at: float | None = None
    pending_notify: bool = False
    opened_at: float = 0.0
    resolved_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Incident:
        return cls(
            id=str(raw["id"]),
            rule=str(raw["rule"]),
            state="resolved" if raw.get("state") == "resolved" else "active",
            message=str(raw.get("message") or ""),
            notified_at=_opt_float(raw.get("notified_at")),
            pending_notify=bool(raw.get("pending_notify")),
            opened_at=float(raw.get("opened_at") or 0.0),
            resolved_at=_opt_float(raw.get("resolved_at")),
        )


@dataclass
class ProbeSnapshot:
    """Resultado da coleta (sem decisão de alerta)."""

    ollama_ok: bool
    ollama_detail: str
    backup_status: Literal["ok", "stale", "unverified"]
    backup_detail: str
    backup_age_hours: float | None = None


@dataclass
class RuleRuntime:
    """Estado por regra (falha contínua, pausa)."""

    paused: bool = False
    fail_since: float | None = None  # epoch; limpo na recuperação


@dataclass
class SentinelRuntime:
    rules: dict[str, RuleRuntime] = field(default_factory=dict)

    def rule(self, rule_id: str) -> RuleRuntime:
        if rule_id not in self.rules:
            self.rules[rule_id] = RuleRuntime()
        return self.rules[rule_id]


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
