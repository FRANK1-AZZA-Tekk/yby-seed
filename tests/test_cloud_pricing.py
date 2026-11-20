"""Estimativa local de custo USD — teto OpenRouter US$10/mês."""

from src.engine.cloud_pricing import estimate_cost, estimate_cost_usd


def test_free_model_costs_zero() -> None:
    est = estimate_cost(
        provider="openrouter",
        model="openrouter/free",
        input_tokens=50_000,
        output_tokens=10_000,
    )
    assert est.usd == 0.0
    assert est.basis == "free"


def test_free_suffix_costs_zero() -> None:
    assert (
        estimate_cost_usd(
            provider="openrouter",
            model="meta-llama/llama-3.3-70b-instruct:free",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        == 0.0
    )
    assert (
        estimate_cost(
            provider="openrouter",
            model="meta-llama/llama-3.3-70b-instruct:free",
            input_tokens=1,
            output_tokens=0,
        ).basis
        == "free"
    )


def test_hermes_matches_planning_doc() -> None:
    # 1M in + 1M out → 0.13 + 0.40
    est = estimate_cost(
        provider="openrouter",
        model="nousresearch/hermes-4-70b",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert est.usd == 0.53
    assert est.basis == "known"


def test_sonnet_substring_match() -> None:
    cost = estimate_cost_usd(
        provider="openrouter",
        model="anthropic/claude-sonnet-4.5",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert cost == 2.0


def test_unknown_paid_uses_conservative_floor() -> None:
    """Não-free desconhecido não pode custar 0 (furaria o teto de US$10)."""

    est = estimate_cost(
        provider="openrouter",
        model="vendor/mystery-paid-model-xyz",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert est.usd == 3.0
    assert est.basis == "unknown_conservative"
