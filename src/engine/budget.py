"""Política local de orçamento de tokens e custo USD de nuvem."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from src.engine.cloud_usage_log import DEFAULT_LOG_PATH, EVENT_COMPLETED

CODE_ALLOWED = "allowed"
CODE_BLOCKED_LOCAL_ONLY = "blocked_local_only"
CODE_BLOCKED_NO_TTY = "blocked_no_tty"
CODE_BLOCKED_BUDGET = "blocked_budget"

# Defaults alinhados a docs/CLOUD_USAGE_SPEC.md §7.1
DEFAULT_DAILY_TOKEN_LIMIT = 50_000
DEFAULT_WARN_DAILY_TOKEN_LIMIT = 40_000
DEFAULT_MONTHLY_TOKEN_LIMIT = 200_000
DEFAULT_WARN_TOKEN_LIMIT = 150_000
DEFAULT_DAILY_COST_USD_LIMIT = 2.0
DEFAULT_MONTHLY_COST_USD_LIMIT = 10.0
DEFAULT_WARN_RATIO = 0.8
DEFAULT_CONFIRM_COST_USD = 0.01
DEFAULT_CONFIRM_TOKEN_THRESHOLD = 2000

_FORCE_CONFIRM_PURPOSES = frozenset({"ollama_fallback", "explicit_paid_model"})


@dataclass(frozen=True)
class BudgetEvaluation:
    allowed: bool
    reason: str
    code: str
    exception_granted: bool = False


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
        daily_cost_usd_limit: float = DEFAULT_DAILY_COST_USD_LIMIT,
        monthly_cost_usd_limit: float = DEFAULT_MONTHLY_COST_USD_LIMIT,
        warn_ratio: float = DEFAULT_WARN_RATIO,
        budget_exception: bool = False,
        confirm_cost_usd: float = DEFAULT_CONFIRM_COST_USD,
        confirm_token_threshold: int = DEFAULT_CONFIRM_TOKEN_THRESHOLD,
    ) -> None:
        self.cloud_mode = cloud_mode.strip().casefold() or "ask"
        self.log_path = log_path
        self.daily_token_limit = daily_token_limit
        self.warn_daily_token_limit = warn_daily_token_limit
        self.monthly_token_limit = monthly_token_limit
        self.warn_token_limit = warn_token_limit
        self.daily_cost_usd_limit = daily_cost_usd_limit
        self.monthly_cost_usd_limit = monthly_cost_usd_limit
        self.warn_ratio = warn_ratio
        self.require_confirm = require_confirm
        self.allow_no_tty = allow_no_tty
        self.confirm_cost_usd = confirm_cost_usd
        self.confirm_token_threshold = confirm_token_threshold
        self._exception_uses_left = 1 if budget_exception else 0
        self._usage_stamp: tuple[int, int] | None = None
        self._usage_day = 0
        self._usage_month = 0
        self._cost_day = 0.0
        self._cost_month = 0.0

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
            daily_cost_usd_limit=_float(
                source, "YBY_CLOUD_DAILY_COST_USD_LIMIT", DEFAULT_DAILY_COST_USD_LIMIT
            ),
            monthly_cost_usd_limit=_float(
                source, "YBY_CLOUD_MONTHLY_COST_USD_LIMIT", DEFAULT_MONTHLY_COST_USD_LIMIT
            ),
            warn_ratio=_float(source, "YBY_CLOUD_WARN_RATIO", DEFAULT_WARN_RATIO),
            require_confirm=_bool(source, "YBY_CLOUD_REQUIRE_CONFIRM", True),
            allow_no_tty=_bool(source, "YBY_CLOUD_ALLOW_NO_TTY", False),
            budget_exception=_bool(source, "YBY_CLOUD_BUDGET_EXCEPTION", False),
            confirm_cost_usd=_float(
                source, "YBY_CLOUD_CONFIRM_COST_USD", DEFAULT_CONFIRM_COST_USD
            ),
            confirm_token_threshold=_int(
                source,
                "YBY_CLOUD_CONFIRM_TOKEN_THRESHOLD",
                DEFAULT_CONFIRM_TOKEN_THRESHOLD,
            ),
        )

    def should_confirm(
        self,
        *,
        input_tokens: int,
        estimated_cost_usd: float,
        purpose: str,
        session_confirmed: bool,
        evaluation: BudgetEvaluation,
    ) -> bool:
        """Política §6.2: quando pedir confirmação antes do HTTP."""

        # Exception explícita já liberou este call — não pedir de novo.
        if evaluation.exception_granted:
            return False

        in_warn = evaluation.reason.startswith("Aviso:")
        token_hit = input_tokens >= self.confirm_token_threshold > 0
        cost_hit = (
            self.confirm_cost_usd > 0 and estimated_cost_usd >= self.confirm_cost_usd
        )
        purpose_hit = purpose.strip() in _FORCE_CONFIRM_PURPOSES

        if in_warn or token_hit or cost_hit or purpose_hit:
            return True
        if self.require_confirm and not session_confirmed:
            return True
        return False

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

        used_day, used_month, cost_day, cost_month = self._usage()

        hard = self._hard_block_reason(used_day, used_month, cost_day, cost_month)
        if hard is not None:
            if self._exception_uses_left > 0:
                self._exception_uses_left -= 1
                return BudgetEvaluation(
                    True,
                    f"Exceção de orçamento concedida (1 uso). Motivo do teto: {hard}",
                    CODE_ALLOWED,
                    exception_granted=True,
                )
            return BudgetEvaluation(False, hard, CODE_BLOCKED_BUDGET)

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

        warn = self._warn_reason(used_day, used_month, cost_day, cost_month)
        if warn is not None:
            return BudgetEvaluation(True, warn, CODE_ALLOWED)
        return BudgetEvaluation(True, "Dentro do orçamento diário/mensal.", CODE_ALLOWED)

    def _hard_block_reason(
        self,
        used_day: int,
        used_month: int,
        cost_day: float,
        cost_month: float,
    ) -> str | None:
        if used_day >= self.daily_token_limit:
            return (
                f"Teto diário de tokens atingido ({used_day}/{self.daily_token_limit})."
            )
        if used_month >= self.monthly_token_limit:
            return (
                f"Teto mensal de tokens atingido ({used_month}/{self.monthly_token_limit})."
            )
        if cost_day >= self.daily_cost_usd_limit > 0:
            return (
                f"Teto diário de custo USD atingido "
                f"(${cost_day:.4f}/${self.daily_cost_usd_limit:.2f})."
            )
        if cost_month >= self.monthly_cost_usd_limit > 0:
            return (
                f"Teto mensal de custo USD atingido "
                f"(${cost_month:.4f}/${self.monthly_cost_usd_limit:.2f})."
            )
        return None

    def _warn_reason(
        self,
        used_day: int,
        used_month: int,
        cost_day: float,
        cost_month: float,
    ) -> str | None:
        if used_day >= self.warn_daily_token_limit:
            return (
                f"Aviso: uso diário {used_day} tokens "
                f"(alerta em {self.warn_daily_token_limit})."
            )
        if used_month >= self.warn_token_limit:
            return (
                f"Aviso: uso mensal {used_month} tokens "
                f"(alerta em {self.warn_token_limit})."
            )
        warn_daily_cost = self.daily_cost_usd_limit * self.warn_ratio
        if self.daily_cost_usd_limit > 0 and cost_day >= warn_daily_cost > 0:
            return (
                f"Aviso: custo diário ${cost_day:.4f} "
                f"(alerta em ${warn_daily_cost:.2f})."
            )
        warn_month_cost = self.monthly_cost_usd_limit * self.warn_ratio
        if self.monthly_cost_usd_limit > 0 and cost_month >= warn_month_cost > 0:
            return (
                f"Aviso: custo mensal ${cost_month:.4f} "
                f"(alerta em ${warn_month_cost:.2f})."
            )
        return None

    def _usage(self) -> tuple[int, int, float, float]:
        """(tokens_dia, tokens_mês, usd_dia, usd_mês) UTC de eventos completed."""
        if not self.log_path.is_file():
            self._usage_stamp = None
            return 0, 0, 0.0, 0.0
        stat = self.log_path.stat()
        stamp = (stat.st_mtime_ns, stat.st_size)
        if stamp == self._usage_stamp:
            return self._usage_day, self._usage_month, self._cost_day, self._cost_month
        day_t, month_t, day_c, month_c = self._scan_usage()
        self._usage_stamp = stamp
        self._usage_day = day_t
        self._usage_month = month_t
        self._cost_day = day_c
        self._cost_month = month_c
        return day_t, month_t, day_c, month_c

    def _scan_usage(self) -> tuple[int, int, float, float]:
        now = time.gmtime()
        year, month, day = now.tm_year, now.tm_mon, now.tm_mday
        day_total = 0
        month_total = 0
        day_cost = 0.0
        month_cost = 0.0
        with self.log_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("result") != EVENT_COMPLETED:
                    continue
                ts = row.get("timestamp")
                if not isinstance(ts, (int, float)):
                    continue
                when = time.gmtime(ts)
                if when.tm_year != year or when.tm_mon != month:
                    continue
                tokens = 0
                for field in ("input_tokens_estimate", "output_tokens_estimate"):
                    value = row.get(field, 0)
                    if isinstance(value, int):
                        tokens += value
                cost = row.get("estimated_cost_usd", 0)
                cost_f = float(cost) if isinstance(cost, (int, float)) else 0.0
                if cost_f < 0:
                    cost_f = 0.0
                month_total += tokens
                month_cost += cost_f
                if when.tm_mday == day:
                    day_total += tokens
                    day_cost += cost_f
        return day_total, month_total, day_cost, month_cost


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


def _float(source: dict[str, str], name: str, default: float) -> float:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
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
