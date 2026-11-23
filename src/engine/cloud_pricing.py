"""Estimativa local de custo USD (advisory; não é fatura).

Tabela mínima em USD por 1M tokens (in/out). Modelos free/desconhecidos → 0.
"""

from __future__ import annotations

# (provider, model) → (usd_per_1m_input, usd_per_1m_output)
_PRICE_TABLE: dict[tuple[str, str], tuple[float, float]] = {
    ("openrouter", "openrouter/free"): (0.0, 0.0),
    ("cache", "*"): (0.0, 0.0),
}


def estimate_cost_usd(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Retorna custo estimado em USD (sempre >= 0)."""

    in_tok = max(0, int(input_tokens))
    out_tok = max(0, int(output_tokens))
    price_in, price_out = _lookup(provider, model)
    cost = (in_tok / 1_000_000.0) * price_in + (out_tok / 1_000_000.0) * price_out
    if cost < 0:
        return 0.0
    return round(cost, 8)


def _lookup(provider: str, model: str) -> tuple[float, float]:
    key = (provider.strip().casefold(), model.strip())
    if key in _PRICE_TABLE:
        return _PRICE_TABLE[key]
    if key[0] == "cache":
        return (0.0, 0.0)
    # free / :free no nome → zero
    if "free" in key[1].casefold():
        return (0.0, 0.0)
    return (0.0, 0.0)
