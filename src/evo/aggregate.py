"""Agregação diária de eventos Evo."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DayAggregate:
    """Resumo de um dia para relatório / prompt local."""

    day: str
    total: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)
    by_severity: dict[str, int] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    sources: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "total": self.total,
            "by_kind": dict(self.by_kind),
            "by_severity": dict(self.by_severity),
            "errors": list(self.errors),
            "problems": list(self.problems),
            "evidence": list(self.evidence),
            "sources": dict(self.sources),
        }


def aggregate_day(day: str, events: list[dict[str, Any]]) -> DayAggregate:
    """Conta kinds/severities e lista problemas + evidências."""

    kinds: Counter[str] = Counter()
    severities: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    errors: list[dict[str, Any]] = []
    problems: list[str] = []
    evidence: list[str] = []

    for event in events:
        kind = str(event.get("kind") or "unknown")
        severity = str(event.get("severity") or "info")
        source = str(event.get("source") or "")
        summary = str(event.get("summary") or "")
        kinds[kind] += 1
        severities[severity] += 1
        if source:
            sources[source] += 1
        evidence.append(f"[{event.get('ts', '?')}] {kind}: {summary}")
        if kind == "error" or severity in {"error", "critical"}:
            errors.append(
                {
                    "ts": event.get("ts"),
                    "summary": summary,
                    "source": source,
                    "payload": event.get("payload") or {},
                }
            )
            problems.append(summary)
        if kind == "cloud_call" and "fail" in summary.casefold():
            problems.append(summary)
        if kind == "test_result":
            payload = event.get("payload") or {}
            failed = payload.get("failed")
            if isinstance(failed, int) and failed > 0:
                problems.append(summary)

    return DayAggregate(
        day=day,
        total=len(events),
        by_kind=dict(kinds),
        by_severity=dict(severities),
        errors=errors,
        problems=problems,
        evidence=evidence,
        sources=dict(sources),
    )
