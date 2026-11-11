"""Orçamento de tokens de nuvem (issue #42)."""

from __future__ import annotations

import json

from src.engine.budget import (
    CODE_BLOCKED_BUDGET,
    CODE_BLOCKED_LOCAL_ONLY,
    CODE_BLOCKED_NO_TTY,
    CloudBudget,
)
from src.engine.cloud_usage_log import EVENT_COMPLETED, utc_timestamp


def test_local_only_bloqueia() -> None:
    budget = CloudBudget.from_env(
        {"YBY_CLOUD_MODE": "local_only", "YBY_CLOUD_REQUIRE_CONFIRM": "1"}
    )
    out = budget.evaluate(requires_confirmation=True, has_tty=True)
    assert out.allowed is False
    assert out.code == CODE_BLOCKED_LOCAL_ONLY


def test_sem_tty_exige_interacao() -> None:
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "ask",
            "YBY_CLOUD_REQUIRE_CONFIRM": "1",
            "YBY_CLOUD_ALLOW_NO_TTY": "0",
        }
    )
    out = budget.evaluate(requires_confirmation=True, has_tty=False)
    assert out.allowed is False
    assert out.code == CODE_BLOCKED_NO_TTY


def test_teto_mensal_bloqueia(tmp_path) -> None:
    log_path = tmp_path / "cloud_usage.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "timestamp": utc_timestamp(),
                "provider": "openrouter",
                "model": "m",
                "purpose": "test",
                "input_tokens_estimate": 150_000,
                "output_tokens_estimate": 60_000,
                "result": EVENT_COMPLETED,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "ask",
            "YBY_CLOUD_LOG_PATH": str(log_path),
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "200000",
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
        }
    )
    out = budget.evaluate(requires_confirmation=False, has_tty=True)
    assert out.allowed is False
    assert out.code == CODE_BLOCKED_BUDGET


def test_dentro_do_teto_permite() -> None:
    budget = CloudBudget.from_env({"YBY_CLOUD_MODE": "ask", "YBY_CLOUD_REQUIRE_CONFIRM": "0"})
    out = budget.evaluate(requires_confirmation=False, has_tty=False)
    assert out.allowed is True
