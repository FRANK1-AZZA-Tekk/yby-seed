"""Persistência de incidentes e runtime (uma fonte por domínio)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.sentinel.models import Incident, RuleRuntime, SentinelRuntime


def load_incidents(path: Path) -> list[Incident]:
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(raw, dict):
        rows = raw.get("incidents", [])
    elif isinstance(raw, list):
        rows = raw
    else:
        return []
    out: list[Incident] = []
    for row in rows:
        if isinstance(row, dict) and "id" in row and "rule" in row:
            try:
                out.append(Incident.from_dict(row))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def save_incidents(path: Path, incidents: list[Incident]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [i.to_dict() for i in incidents]
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_runtime(path: Path) -> SentinelRuntime:
    if not path.is_file():
        return SentinelRuntime()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return SentinelRuntime()
    if not isinstance(raw, dict):
        return SentinelRuntime()
    rules_raw = raw.get("rules") or {}
    runtime = SentinelRuntime()
    if isinstance(rules_raw, dict):
        for key, val in rules_raw.items():
            if not isinstance(val, dict):
                continue
            runtime.rules[str(key)] = RuleRuntime(
                paused=bool(val.get("paused")),
                fail_since=_opt_float(val.get("fail_since")),
            )
    return runtime


def save_runtime(path: Path, runtime: SentinelRuntime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rules: dict[str, Any] = {}
    for key, rr in runtime.rules.items():
        rules[key] = {"paused": rr.paused, "fail_since": rr.fail_since}
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps({"rules": rules}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def active_for_rule(incidents: list[Incident], rule: str) -> Incident | None:
    for inc in incidents:
        if inc.rule == rule and inc.state == "active":
            return inc
    return None


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
