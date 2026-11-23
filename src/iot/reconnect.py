"""Backoff exponencial para reconexão MQTT (com jitter)."""

from __future__ import annotations

import random


def next_reconnect_delay(
    attempt: int,
    *,
    base_seconds: float = 1.0,
    max_seconds: float = 60.0,
    rng: random.Random | None = None,
) -> float:
    """
    ``attempt`` começa em 0 após a primeira queda (1s, 2s, 4s, 8s…).

    Jitter até 25%% do atraso base para evitar thundering herd.
    """

    if attempt < 0:
        attempt = 0
    exp = min(base_seconds * (2**attempt), max_seconds)
    jitter_span = exp * 0.25
    generator = rng if rng is not None else random
    return exp + generator.uniform(0.0, jitter_span)