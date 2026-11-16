"""Leitura e resumo do cloud_usage.jsonl + orçamento mensal."""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.engine.budget import CloudBudget
from src.engine.cloud_usage_log import EVENT_COMPLETED, TOKENS_SOURCE_API


class UsageError(ValueError):
    """Falha ao ler ou resumir uso local."""


@dataclass(frozen=True)
class UsageReport:
    log_path: Path
    cloud_mode: str
    month_tokens: int
    monthly_token_limit: int
    warn_token_limit: int
    event_count: int
    by_result: dict[str, int]
    completed_count: int
    blocked_count: int
    failed_count: int


def read_events(log_path: Path) -> list[dict[str, Any]]:
    """Lê JSONL; linhas inválidas são ignoradas."""

    if not log_path.is_file():
        return []
    events: list[dict[str, Any]] = []
    with log_path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                events.append(row)
    return events


def summarize(
    *,
    log_path: Path,
    budget: CloudBudget | None = None,
    events: list[dict[str, Any]] | None = None,
) -> UsageReport:
    rows = events if events is not None else read_events(log_path)
    budget = budget or CloudBudget.from_env({"YBY_CLOUD_LOG_PATH": str(log_path)})
    month = budget.month_usage()
    by_result = Counter(
        str(row.get("result") or "unknown") for row in rows if row.get("result") is not None
    )
    blocked = sum(count for key, count in by_result.items() if "blocked" in key)
    failed = by_result.get("cloud_failed", 0)
    return UsageReport(
        log_path=log_path,
        cloud_mode=month.cloud_mode,
        month_tokens=month.tokens,
        monthly_token_limit=month.monthly_token_limit,
        warn_token_limit=month.warn_token_limit,
        event_count=len(rows),
        by_result=dict(sorted(by_result.items())),
        completed_count=by_result.get(EVENT_COMPLETED, 0),
        blocked_count=blocked,
        failed_count=failed,
    )


def format_summary(report: UsageReport) -> str:
    warn = ""
    if report.month_tokens >= report.monthly_token_limit:
        warn = " [TETO]"
    elif report.month_tokens >= report.warn_token_limit:
        warn = " [AVISO]"
    lines = [
        f"log: {report.log_path}",
        f"modo: {report.cloud_mode}",
        (
            f"mês UTC: {report.month_tokens}/{report.monthly_token_limit} tokens"
            f" (aviso {report.warn_token_limit}){warn}"
        ),
        (
            f"eventos: {report.event_count} "
            f"(completed={report.completed_count}, "
            f"blocked={report.blocked_count}, failed={report.failed_count})"
        ),
    ]
    if report.by_result:
        breakdown = ", ".join(f"{key}={count}" for key, count in report.by_result.items())
        lines.append(f"por resultado: {breakdown}")
    else:
        lines.append("por resultado: (vazio)")
    return "\n".join(lines)


def format_events(events: list[dict[str, Any]], *, limit: int = 20) -> str:
    if limit < 1:
        raise UsageError("--limit deve ser >= 1")
    if not events:
        return "(nenhum evento)"
    selected = events[-limit:]
    lines: list[str] = []
    for row in selected:
        ts = row.get("timestamp")
        when = _fmt_ts(ts)
        result = row.get("result", "?")
        provider = row.get("provider", "?")
        model = row.get("model", "?")
        purpose = row.get("purpose", "?")
        tokens = _row_tokens(row) if row.get("result") == EVENT_COMPLETED else 0
        token_bit = f" tokens={tokens}" if tokens else ""
        lines.append(
            f"{when}\t{result}\t{provider}/{model}\t{purpose}{token_bit}"
        )
    return "\n".join(lines)


def _fmt_ts(ts: object) -> str:
    if isinstance(ts, (int, float)):
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
    return "?"


def _row_tokens(row: dict[str, Any]) -> int:
    """Mesma preferência API→estimativa do CloudBudget."""

    if row.get("tokens_source") == TOKENS_SOURCE_API:
        total = 0
        for field in ("input_tokens", "output_tokens"):
            value = row.get(field, 0)
            if isinstance(value, int):
                total += value
        return total
    total = 0
    for field in ("input_tokens_estimate", "output_tokens_estimate"):
        value = row.get(field, 0)
        if isinstance(value, int):
            total += value
    return total
