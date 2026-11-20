"""Relatório local de uso de nuvem (CLOUD_USAGE_SPEC S5 / #42).

Somente disco local — sem telemetria remota.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from src.engine.budget import (
    DEFAULT_DAILY_COST_USD_LIMIT,
    DEFAULT_DAILY_TOKEN_LIMIT,
    DEFAULT_MONTHLY_COST_USD_LIMIT,
    DEFAULT_MONTHLY_TOKEN_LIMIT,
    CloudBudget,
)
from src.engine.cloud_usage_db import (
    DEFAULT_DB_PATH,
    CloudUsageRegistry,
    retention_days_from_env,
)
from src.engine.cloud_usage_log import DEFAULT_LOG_PATH


@dataclass(frozen=True)
class CloudUsageReport:
    """Snapshot honesto do FinOps local."""

    db_path: Path | None
    db_enabled: bool
    db_exists: bool
    jsonl_path: Path
    jsonl_exists: bool
    jsonl_mirror: bool
    cloud_mode: str
    allow_vault: bool
    retention_days: int
    event_count: int
    by_status: dict[str, int]
    day_tokens: int
    month_tokens: int
    day_cost_usd: float
    month_cost_usd: float
    daily_token_limit: int
    monthly_token_limit: int
    daily_cost_usd_limit: float
    monthly_cost_usd_limit: float


def _bool(source: dict[str, str], name: str, default: bool) -> bool:
    raw = source.get(name, "").strip().casefold()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "sim"}


def build_cloud_usage_report(
    environ: dict[str, str] | None = None,
    *,
    now: float | None = None,
) -> CloudUsageReport:
    """Lê registry/budget do ambiente e monta o relatório."""

    source = environ if environ is not None else os.environ
    log_path = Path(
        source.get("YBY_CLOUD_LOG_PATH", DEFAULT_LOG_PATH).strip() or DEFAULT_LOG_PATH
    )
    db_raw = source.get("YBY_CLOUD_DB_PATH", DEFAULT_DB_PATH).strip()
    db_enabled = db_raw.casefold() not in {"", "0", "off", "-", "none"}
    if not db_raw:
        db_raw = DEFAULT_DB_PATH
    db_path = Path(db_raw) if db_enabled else None
    mirror = _bool(source, "YBY_CLOUD_JSONL_MIRROR", False)
    allow_vault = _bool(source, "YBY_CLOUD_ALLOW_VAULT", False)
    retention = retention_days_from_env(source)
    budget = CloudBudget.from_env(source)

    event_count = 0
    by_status: dict[str, int] = {}
    day_tokens = 0
    month_tokens = 0
    day_cost = 0.0
    month_cost = 0.0
    db_exists = False

    if db_enabled and db_path is not None:
        db_exists = db_path.is_file()
        if db_exists:
            reg = CloudUsageRegistry(db_path)
            try:
                event_count = reg.count_events()
                by_status = reg.count_by_status()
                totals = reg.sum_completed_usage(now=now)
                day_tokens = totals.day_tokens
                month_tokens = totals.month_tokens
                day_cost = totals.day_cost_usd
                month_cost = totals.month_cost_usd
            finally:
                reg.close()

    return CloudUsageReport(
        db_path=db_path,
        db_enabled=db_enabled,
        db_exists=db_exists,
        jsonl_path=log_path,
        jsonl_exists=log_path.is_file(),
        jsonl_mirror=mirror,
        cloud_mode=budget.cloud_mode,
        allow_vault=allow_vault,
        retention_days=retention,
        event_count=event_count,
        by_status=by_status,
        day_tokens=day_tokens,
        month_tokens=month_tokens,
        day_cost_usd=day_cost,
        month_cost_usd=month_cost,
        daily_token_limit=budget.daily_token_limit or DEFAULT_DAILY_TOKEN_LIMIT,
        monthly_token_limit=budget.monthly_token_limit or DEFAULT_MONTHLY_TOKEN_LIMIT,
        daily_cost_usd_limit=budget.daily_cost_usd_limit or DEFAULT_DAILY_COST_USD_LIMIT,
        monthly_cost_usd_limit=(
            budget.monthly_cost_usd_limit or DEFAULT_MONTHLY_COST_USD_LIMIT
        ),
    )


def format_cloud_usage_report(report: CloudUsageReport) -> str:
    """Texto curto para CLI (sem segredos)."""

    lines = [
        "YBY cloud usage (local)",
        f"  mode: {report.cloud_mode}",
        f"  allow_vault: {'1' if report.allow_vault else '0'}",
        f"  jsonl_mirror: {'1' if report.jsonl_mirror else '0'}",
        f"  retention_days: {report.retention_days}",
        f"  jsonl: {report.jsonl_path}"
        + (" (exists)" if report.jsonl_exists else " (missing)"),
    ]
    if not report.db_enabled:
        lines.append("  db: off")
    else:
        assert report.db_path is not None
        lines.append(
            f"  db: {report.db_path}"
            + (" (exists)" if report.db_exists else " (missing)")
        )
        lines.append(f"  events: {report.event_count}")
        if report.by_status:
            status_bits = ", ".join(
                f"{name}={count}" for name, count in sorted(report.by_status.items())
            )
            lines.append(f"  by_status: {status_bits}")
        lines.append(
            f"  day: {report.day_tokens}/{report.daily_token_limit} tok, "
            f"${report.day_cost_usd:.4f}/${report.daily_cost_usd_limit:.2f}"
        )
        lines.append(
            f"  month: {report.month_tokens}/{report.monthly_token_limit} tok, "
            f"${report.month_cost_usd:.4f}/${report.monthly_cost_usd_limit:.2f}"
        )
    return "\n".join(lines) + "\n"
