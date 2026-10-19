"""Cálculo simples de custo da Camada 0."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preco:
    entrada_por_milhao: float = 0.0
    saida_por_milhao: float = 0.0


PRECOS: dict[str, Preco] = {
    "fake": Preco(),
    "ollama": Preco(),
}


def estimar_custo(
    provedor: str,
    tokens_entrada: int,
    tokens_saida: int,
) -> float:
    """Estima o custo em dólares de uma chamada de modelo."""

    preco = PRECOS.get(provedor, Preco())
    return (
        tokens_entrada * preco.entrada_por_milhao / 1_000_000
        + tokens_saida * preco.saida_por_milhao / 1_000_000
    )
