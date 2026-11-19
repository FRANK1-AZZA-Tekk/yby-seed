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
            # Diário alto para isolar o teto mensal neste caso.
            "YBY_CLOUD_DAILY_TOKEN_LIMIT": "500000",
            "YBY_CLOUD_WARN_DAILY_TOKEN_LIMIT": "400000",
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "200000",
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
        }
    )
    out = budget.evaluate(requires_confirmation=False, has_tty=True)
    assert out.allowed is False
    assert out.code == CODE_BLOCKED_BUDGET
    assert "mensal" in out.reason


def test_limite_invalido_cai_no_padrao() -> None:
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "nao",
            "YBY_CLOUD_WARN_TOKEN_LIMIT": "-3",
            "YBY_CLOUD_DAILY_TOKEN_LIMIT": "x",
            "YBY_CLOUD_WARN_DAILY_TOKEN_LIMIT": "-1",
        }
    )
    assert budget.monthly_token_limit == 200_000
    assert budget.warn_token_limit == 150_000
    assert budget.daily_token_limit == 50_000
    assert budget.warn_daily_token_limit == 40_000


def test_dentro_do_teto_permite() -> None:
    budget = CloudBudget.from_env({"YBY_CLOUD_MODE": "ask", "YBY_CLOUD_REQUIRE_CONFIRM": "0"})
    out = budget.evaluate(requires_confirmation=False, has_tty=False)
    assert out.allowed is True


def test_teto_diario_bloqueia(tmp_path) -> None:
    log_path = tmp_path / "cloud_usage.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "timestamp": utc_timestamp(),
                "provider": "openrouter",
                "model": "m",
                "purpose": "test",
                "input_tokens_estimate": 40_000,
                "output_tokens_estimate": 15_000,
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
            "YBY_CLOUD_DAILY_TOKEN_LIMIT": "50000",
            "YBY_CLOUD_WARN_DAILY_TOKEN_LIMIT": "40000",
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "200000",
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
        }
    )
    out = budget.evaluate(requires_confirmation=False, has_tty=True)
    assert out.allowed is False
    assert out.code == CODE_BLOCKED_BUDGET
    assert "diário" in out.reason


def test_aviso_diario_permite_com_razao(tmp_path) -> None:
    log_path = tmp_path / "cloud_usage.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "timestamp": utc_timestamp(),
                "provider": "openrouter",
                "model": "m",
                "purpose": "test",
                "input_tokens_estimate": 42_000,
                "output_tokens_estimate": 0,
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
            "YBY_CLOUD_DAILY_TOKEN_LIMIT": "50000",
            "YBY_CLOUD_WARN_DAILY_TOKEN_LIMIT": "40000",
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "200000",
            "YBY_CLOUD_WARN_TOKEN_LIMIT": "150000",
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
        }
    )
    out = budget.evaluate(requires_confirmation=False, has_tty=True)
    assert out.allowed is True
    assert out.reason.startswith("Aviso:")
    assert "diário" in out.reason


def test_teto_diario_usd_bloqueia(tmp_path) -> None:
    log_path = tmp_path / "cloud_usage.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "timestamp": utc_timestamp(),
                "provider": "openrouter",
                "model": "paid",
                "purpose": "test",
                "input_tokens_estimate": 10,
                "output_tokens_estimate": 10,
                "estimated_cost_usd": 2.5,
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
            "YBY_CLOUD_DAILY_TOKEN_LIMIT": "500000",
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "500000",
            "YBY_CLOUD_DAILY_COST_USD_LIMIT": "2.00",
            "YBY_CLOUD_MONTHLY_COST_USD_LIMIT": "10.00",
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
        }
    )
    out = budget.evaluate(requires_confirmation=False, has_tty=True)
    assert out.allowed is False
    assert out.code == CODE_BLOCKED_BUDGET
    assert "custo" in out.reason.casefold()
    assert "diário" in out.reason


def test_excecao_libera_um_uso_apos_teto(tmp_path) -> None:
    log_path = tmp_path / "cloud_usage.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "timestamp": utc_timestamp(),
                "provider": "openrouter",
                "model": "paid",
                "purpose": "test",
                "input_tokens_estimate": 10,
                "output_tokens_estimate": 10,
                "estimated_cost_usd": 5.0,
                "result": EVENT_COMPLETED,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    env = {
        "YBY_CLOUD_MODE": "ask",
        "YBY_CLOUD_LOG_PATH": str(log_path),
        "YBY_CLOUD_DAILY_TOKEN_LIMIT": "500000",
        "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "500000",
        "YBY_CLOUD_DAILY_COST_USD_LIMIT": "2.00",
        "YBY_CLOUD_REQUIRE_CONFIRM": "0",
        "YBY_CLOUD_BUDGET_EXCEPTION": "1",
    }
    budget = CloudBudget.from_env(env)
    first = budget.evaluate(requires_confirmation=False, has_tty=True)
    assert first.allowed is True
    assert first.exception_granted is True
    second = budget.evaluate(requires_confirmation=False, has_tty=True)
    assert second.allowed is False
    assert second.code == CODE_BLOCKED_BUDGET


def test_excecao_nao_bypassa_local_only() -> None:
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "local_only",
            "YBY_CLOUD_BUDGET_EXCEPTION": "1",
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
        }
    )
    out = budget.evaluate(requires_confirmation=False, has_tty=True)
    assert out.allowed is False
    assert out.code == CODE_BLOCKED_LOCAL_ONLY
    assert out.exception_granted is False


def test_aviso_mensal_permite_com_razao(tmp_path) -> None:
    log_path = tmp_path / "cloud_usage.jsonl"
    # Abaixo do teto/aviso diário; acima do aviso mensal.
    log_path.write_text(
        json.dumps(
            {
                "timestamp": utc_timestamp(),
                "provider": "openrouter",
                "model": "m",
                "purpose": "test",
                "input_tokens_estimate": 160_000,
                "output_tokens_estimate": 0,
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
            "YBY_CLOUD_DAILY_TOKEN_LIMIT": "500000",
            "YBY_CLOUD_WARN_DAILY_TOKEN_LIMIT": "400000",
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "200000",
            "YBY_CLOUD_WARN_TOKEN_LIMIT": "150000",
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
        }
    )
    out = budget.evaluate(requires_confirmation=False, has_tty=True)
    assert out.allowed is True
    assert out.reason.startswith("Aviso:")
    assert "mensal" in out.reason
