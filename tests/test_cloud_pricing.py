"""Estimativa local de custo USD."""

from src.engine.cloud_pricing import estimate_cost_usd


def test_free_model_costs_zero() -> None:
    assert (
        estimate_cost_usd(
            provider="openrouter",
            model="openrouter/free",
            input_tokens=50_000,
            output_tokens=10_000,
        )
        == 0.0
    )


def test_unknown_model_defaults_to_zero() -> None:
    assert (
        estimate_cost_usd(
            provider="openrouter",
            model="unknown/paid-ish",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        == 0.0
    )
