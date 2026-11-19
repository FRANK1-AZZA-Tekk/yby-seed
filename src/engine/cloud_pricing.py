"""Estimativa local de custo USD (advisory; não é fatura).

Política do dono: teto OpenRouter **US$ 10/mês** (`YBY_CLOUD_MONTHLY_COST_USD_LIMIT`).
Preços de referência alinhados a `docs/PLANEJAMENTO-CUSTOS-IA.md`.
Modelos desconhecidos (não-free) usam fallback conservador (faixa Sonnet)
para o orçamento não subestimar gasto real.
"""

from __future__ import annotations

# USD por 1M tokens (input, output) — OpenRouter ref. out/2026
_PRICE_TABLE: dict[tuple[str, str], tuple[float, float]] = {
    ("openrouter", "openrouter/free"): (0.0, 0.0),
    ("cache", "*"): (0.0, 0.0),
    # Econômicos
    ("openrouter", "nousresearch/hermes-4-70b"): (0.13, 0.40),
    ("openrouter", "deepseek/deepseek-chat-v3.1"): (0.25, 0.95),
    ("openrouter", "meta-llama/llama-3.3-70b-instruct"): (0.10, 0.32),
    ("openrouter", "qwen/qwen3-coder"): (0.30, 1.00),
    # Premium
    ("openrouter", "anthropic/claude-sonnet-4.5"): (2.00, 10.00),
    ("openrouter", "anthropic/claude-3.5-sonnet"): (3.00, 15.00),
    ("openrouter", "anthropic/claude-sonnet-4"): (3.00, 15.00),
}

# Substring match (model id contém a chave) → preços
_SUBSTRING_PRICES: tuple[tuple[str, tuple[float, float]], ...] = (
    ("hermes-4-70b", (0.13, 0.40)),
    ("hermes-3-70b", (0.13, 0.40)),
    ("deepseek-chat", (0.25, 0.95)),
    ("deepseek-v3", (0.25, 0.95)),
    ("llama-3.3-70b", (0.10, 0.32)),
    ("qwen3-coder", (0.30, 1.00)),
    ("claude-sonnet-4.5", (2.00, 10.00)),
    ("claude-3.5-sonnet", (3.00, 15.00)),
    ("claude-sonnet", (3.00, 15.00)),
    ("claude-opus", (15.00, 75.00)),
)

# Desconhecido pago: assume faixa Sonnet para não furar o teto de US$10/mês.
_UNKNOWN_PAID: tuple[float, float] = (3.00, 15.00)


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
    prov = provider.strip().casefold()
    model_id = model.strip()
    key = (prov, model_id)
    if key in _PRICE_TABLE:
        return _PRICE_TABLE[key]
    if prov == "cache" or model_id == "*":
        return (0.0, 0.0)
    folded = model_id.casefold()
    if "free" in folded or folded.endswith(":free"):
        return (0.0, 0.0)
    for needle, prices in _SUBSTRING_PRICES:
        if needle in folded:
            return prices
    # openrouter / cloud genérico sem preço conhecido → conservador
    if prov in {"openrouter", "cloud", "xai", "grok"}:
        return _UNKNOWN_PAID
    return _UNKNOWN_PAID
