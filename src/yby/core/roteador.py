"""Roteador mínimo de modelos do YBY SEED."""

from __future__ import annotations

from math import isfinite

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
    """Escolhe o provedor e verifica o limite de custo por pedido."""

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

    def validar_custo_previsto(self, custo_usd: float) -> None:
        """Impede uma chamada com estimativa acima do teto configurado."""
        self._validar_valor(custo_usd)
        if custo_usd > self.config.teto_custo_por_pedido:
            raise ValueError(
                LIMITE_PEDIDO.format(
                    custo=custo_usd, teto=self.config.teto_custo_por_pedido
                )
            )

    def validar_custo(self, resposta: Resposta) -> None:
        """Verifica o custo informado pelo provedor e a estimativa por tokens.

        Esta verificação posterior é auditoria; não desfaz uma cobrança remota.
        """
        self._validar_valor(resposta.custo_usd)
        estimado = estimar_custo(
            resposta.provedor, resposta.tokens_entrada, resposta.tokens_saida
        )
        self._validar_valor(estimado)
        self.validar_custo_previsto(max(resposta.custo_usd, estimado))

    @staticmethod
    def _validar_valor(custo_usd: float) -> None:
        if not isfinite(custo_usd) or custo_usd < 0:
            raise ValueError("Custo inválido: informe valor finito e não negativo.")
