"""Roteador mínimo de modelos do YBY SEED."""

from __future__ import annotations

from math import isfinite

from ..config import Config
from ..messages import LIMITE_DIARIO, LIMITE_PEDIDO
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
    """Escolhe o provedor e verifica os limites de custo."""

    def __init__(self, config: Config, banco=None) -> None:
        self.config = config
        self.banco = banco

    def resolver_provedor(self, nome: str | None = None) -> Provedor:
        """Retorna uma instância do provedor solicitado ou padrão."""

        nome = nome or self.config.provedor_padrao

        if self.config.modo_economia and nome not in {"fake", "ollama"}:
            nome = "fake"

        if nome not in PROVEDORES:
            raise ValueError(f"Provedor desconhecido: {nome}")

        return PROVEDORES[nome](self.config)

    def validar_custo_previsto(
        self,
        custo_usd: float,
        criado_em: str | None = None,
    ) -> None:
        """Impede uma chamada acima do teto por pedido ou do teto diário."""

        self._validar_valor(custo_usd)
        self._validar_teto_por_pedido(custo_usd)
        self._validar_teto_diario(custo_usd, criado_em)

    def validar_custo(self, resposta: Resposta) -> None:
        """Audita o custo retornado pelo provedor e a estimativa por tokens."""

        self._validar_valor(resposta.custo_usd)
        estimado = estimar_custo(
            resposta.provedor,
            resposta.tokens_entrada,
            resposta.tokens_saida,
        )
        self._validar_valor(estimado)
        self._validar_teto_por_pedido(max(resposta.custo_usd, estimado))

    def _validar_teto_por_pedido(self, custo_usd: float) -> None:
        if custo_usd > self.config.teto_custo_por_pedido:
            raise ValueError(
                LIMITE_PEDIDO.format(
                    custo=custo_usd,
                    teto=self.config.teto_custo_por_pedido,
                )
            )

    def _validar_teto_diario(
        self,
        custo_usd: float,
        criado_em: str | None,
    ) -> None:
        if self.banco is None:
            return

        gasto_atual = self.banco.gasto_do_dia(criado_em)

        if gasto_atual + custo_usd > self.config.teto_custo_diario:
            raise ValueError(
                LIMITE_DIARIO.format(
                    gasto=gasto_atual,
                    custo=custo_usd,
                    teto=self.config.teto_custo_diario,
                )
            )

    @staticmethod
    def _validar_valor(custo_usd: float) -> None:
        if not isfinite(custo_usd) or custo_usd < 0:
            raise ValueError("Custo inválido: informe valor finito e não negativo.")
