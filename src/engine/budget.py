"""Política local de orçamento de tokens de nuvem (sem custo em BRL)."""

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
        monthly_token_limit: int,
        warn_token_limit: int,
        require_confirm: bool,
        allow_no_tty: bool,
    ) -> None:
        self.cloud_mode = cloud_mode.strip().casefold() or "ask"
        self.log_path = log_path
        self.monthly_token_limit = monthly_token_limit
        self.warn_token_limit = warn_token_limit
        self.require_confirm = require_confirm
        self.allow_no_tty = allow_no_tty

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> CloudBudget:
        source = environ if environ is not None else os.environ
        log_path = Path(
            source.get("YBY_CLOUD_LOG_PATH", DEFAULT_LOG_PATH).strip() or DEFAULT_LOG_PATH
        )
        return cls(
            cloud_mode=source.get("YBY_CLOUD_MODE", "ask"),
            log_path=log_path,
            monthly_token_limit=_int(source, "YBY_CLOUD_MONTHLY_TOKEN_LIMIT", 200_000),
            warn_token_limit=_int(source, "YBY_CLOUD_WARN_TOKEN_LIMIT", 150_000),
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

        used = self._month_token_usage()
        if used >= self.monthly_token_limit:
            return BudgetEvaluation(
                False,
                f"Teto mensal de tokens atingido ({used}/{self.monthly_token_limit}).",
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

        if used >= self.warn_token_limit:
            return BudgetEvaluation(
                True,
                f"Aviso: uso mensal {used} tokens (alerta em {self.warn_token_limit}).",
                CODE_ALLOWED,
            )
        return BudgetEvaluation(True, "Dentro do orçamento mensal.", CODE_ALLOWED)

    def _month_token_usage(self) -> int:
        if not self.log_path.is_file():
            return 0
        now = time.gmtime()
        year, month = now.tm_year, now.tm_mon
        total = 0
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
                for field in ("input_tokens_estimate", "output_tokens_estimate"):
                    value = row.get(field, 0)
                    if isinstance(value, int):
                        total += value
        return total


def _int(source: dict[str, str], name: str, default: int) -> int:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _bool(source: dict[str, str], name: str, default: bool) -> bool:
    raw = source.get(name, "").strip().casefold()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "sim"}
