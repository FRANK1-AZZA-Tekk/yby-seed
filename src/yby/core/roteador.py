"""Roteador mínimo de modelos do YBY SEED."""

from __future__ import annotations

from ..config import Config
from ..messages import LIMITE_PEDIDO
from ..models import Resposta
from ..providers.base import Provedor
from ..providers.fake import ProvedorFake
from ..providers.ollama import ProvedorOllama
from ..providers.openrouter import ProvedorOpenRouter
from .custo import estimar_custo

PROVEDORES: dict[str, type[Provedor]] = {
    "fake": ProvedorFake,
    "ollama": ProvedorOllama,
    "openrouter": ProvedorOpenRouter,
}


class Roteador:
    """Escolhe o provedor e aplica limites de custo."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def resolver_provedor(self, nome: str | None = None) -> Provedor:
        """Retorna uma instância do provedor solicitado ou padrão."""

        nome = nome or self.config.provedor_padrao

        if self.config.modo_economia and nome not in {"fake", "ollama"}:
            nome = "fake"

        if nome not in PROVEDORES:
            raise ValueError(f"Provedor desconhecido: {nome}")

        return PROVEDORES[nome](self.config)

    def validar_custo(self, resposta: Resposta) -> None:
        """Garante que a resposta respeita o teto por pedido."""

        custo = estimar_custo(
            resposta.provedor,
            resposta.tokens_entrada,
            resposta.tokens_saida,
        )

        if custo > self.config.teto_custo_por_pedido:
            raise ValueError(
                LIMITE_PEDIDO.format(
                    custo=custo,
                    teto=self.config.teto_custo_por_pedido,
                )
            )
