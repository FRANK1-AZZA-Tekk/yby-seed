"""Política local de orçamento de tokens de nuvem (sem custo em BRL)."""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path

from src.engine.cloud_usage_log import DEFAULT_LOG_PATH, EVENT_COMPLETED

CODE_ALLOWED = "allowed"
CODE_BLOCKED_LOCAL_ONLY = "blocked_local_only"
CODE_BLOCKED_NO_TTY = "blocked_no_tty"
CODE_BLOCKED_BUDGET = "blocked_budget"

# Defaults alinhados a docs/CLOUD_USAGE_SPEC.md §7.1 (tokens; custo/exception = S2 restante).
DEFAULT_DAILY_TOKEN_LIMIT = 50_000
DEFAULT_WARN_DAILY_TOKEN_LIMIT = 40_000
DEFAULT_MONTHLY_TOKEN_LIMIT = 200_000
DEFAULT_WARN_TOKEN_LIMIT = 150_000


@dataclass(frozen=True)
class BudgetEvaluation:
    allowed: bool
    reason: str
    code: str


class CloudBudget:
    def __init__(
        self,
        *,
        cloud_mode: str,
        log_path: Path,
        daily_token_limit: int,
        warn_daily_token_limit: int,
        monthly_token_limit: int,
        warn_token_limit: int,
        require_confirm: bool,
        allow_no_tty: bool,
    ) -> None:
        self.cloud_mode = cloud_mode.strip().casefold() or "ask"
        self.log_path = log_path
        self.daily_token_limit = daily_token_limit
        self.warn_daily_token_limit = warn_daily_token_limit
        self.monthly_token_limit = monthly_token_limit
        self.warn_token_limit = warn_token_limit
        self.require_confirm = require_confirm
        self.allow_no_tty = allow_no_tty
        self._usage_stamp: tuple[int, int, int, int, int] | None = None
        self._usage_day = 0
        self._usage_month = 0

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> CloudBudget:
        source = environ if environ is not None else os.environ
        log_path = Path(
            source.get("YBY_CLOUD_LOG_PATH", DEFAULT_LOG_PATH).strip() or DEFAULT_LOG_PATH
        )
        return cls(
            cloud_mode=source.get("YBY_CLOUD_MODE", "ask"),
            log_path=log_path,
            daily_token_limit=_int(
                source, "YBY_CLOUD_DAILY_TOKEN_LIMIT", DEFAULT_DAILY_TOKEN_LIMIT
            ),
            warn_daily_token_limit=_int(
                source, "YBY_CLOUD_WARN_DAILY_TOKEN_LIMIT", DEFAULT_WARN_DAILY_TOKEN_LIMIT
            ),
            monthly_token_limit=_int(
                source, "YBY_CLOUD_MONTHLY_TOKEN_LIMIT", DEFAULT_MONTHLY_TOKEN_LIMIT
            ),
            warn_token_limit=_int(
                source, "YBY_CLOUD_WARN_TOKEN_LIMIT", DEFAULT_WARN_TOKEN_LIMIT
            ),
            require_confirm=_bool(source, "YBY_CLOUD_REQUIRE_CONFIRM", True),
            allow_no_tty=_bool(source, "YBY_CLOUD_ALLOW_NO_TTY", False),
        )

    def evaluate(
        self,
        *,
        requires_confirmation: bool,
        has_tty: bool,
    ) -> BudgetEvaluation:
        if self.cloud_mode == "local_only":
            return BudgetEvaluation(
                False,
                "YBY_CLOUD_MODE=local_only: nuvem desabilitada.",
                CODE_BLOCKED_LOCAL_ONLY,
            )

        used_day, used_month = self._token_usage()
        if used_day >= self.daily_token_limit:
            return BudgetEvaluation(
                False,
                f"Teto diário de tokens atingido ({used_day}/{self.daily_token_limit}).",
                CODE_BLOCKED_BUDGET,
            )
        if used_month >= self.monthly_token_limit:
            return BudgetEvaluation(
                False,
                f"Teto mensal de tokens atingido ({used_month}/{self.monthly_token_limit}).",
                CODE_BLOCKED_BUDGET,
            )

        if (
            requires_confirmation
            and self.require_confirm
            and not has_tty
            and not self.allow_no_tty
        ):
            return BudgetEvaluation(
                False,
                "Confirmação de nuvem exige TTY (stdin/stdout interativo).",
                CODE_BLOCKED_NO_TTY,
            )

        if used_day >= self.warn_daily_token_limit:
            return BudgetEvaluation(
                True,
                (
                    f"Aviso: uso diário {used_day} tokens "
                    f"(alerta em {self.warn_daily_token_limit})."
                ),
                CODE_ALLOWED,
            )
        if used_month >= self.warn_token_limit:
            return BudgetEvaluation(
                True,
                (
                    f"Aviso: uso mensal {used_month} tokens "
                    f"(alerta em {self.warn_token_limit})."
                ),
                CODE_ALLOWED,
            )
        return BudgetEvaluation(True, "Dentro do orçamento diário/mensal.", CODE_ALLOWED)

    def _token_usage(self) -> tuple[int, int]:
        """Retorna (tokens_dia_UTC, tokens_mês_UTC) de eventos completed."""
        if not self.log_path.is_file():
            self._usage_stamp = None
            return 0, 0
        now = time.gmtime()
        stat = self.log_path.stat()
        stamp = (stat.st_mtime_ns, stat.st_size, now.tm_year, now.tm_mon, now.tm_mday)
        if stamp == self._usage_stamp:
            return self._usage_day, self._usage_month
        day_total, month_total = self._scan_usage()
        self._usage_stamp = stamp
        self._usage_day = day_total
        self._usage_month = month_total
        return day_total, month_total

    def _scan_usage(self) -> tuple[int, int]:
        now = time.gmtime()
        year, month, day = now.tm_year, now.tm_mon, now.tm_mday
        day_total = 0
        month_total = 0
        with self.log_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                if row.get("result") != EVENT_COMPLETED:
                    continue
                ts = row.get("timestamp")
                if isinstance(ts, bool) or not isinstance(ts, (int, float)) or not math.isfinite(ts):
                    continue
                try:
                    when = time.gmtime(ts)
                except (OSError, OverflowError, ValueError):
                    continue
                if when.tm_year != year or when.tm_mon != month:
                    continue
                tokens = 0
                for field in ("input_tokens_estimate", "output_tokens_estimate"):
                    value = row.get(field, 0)
                    if not isinstance(value, bool) and isinstance(value, int) and value > 0:
                        tokens += value
                month_total += tokens
                if when.tm_mday == day:
                    day_total += tokens
        return day_total, month_total


def _int(source: dict[str, str], name: str, default: int) -> int:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value < 0:
        return default
    return value


def _bool(source: dict[str, str], name: str, default: bool) -> bool:
    raw = source.get(name, "").strip().casefold()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "sim"}
