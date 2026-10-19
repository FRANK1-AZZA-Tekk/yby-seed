"""Provedor fake, determinístico e gratuito para testes."""

from __future__ import annotations

from ..models import Resposta
from .base import Provedor


class ProvedorFake(Provedor):
    """Provedor usado para desenvolvimento e CI sem rede."""

    @property
    def nome(self) -> str:
        return "fake"

    def gerar(self, prompt: str) -> Resposta:
        texto = (
            "YBY SEED recebeu seu pedido e está operando na Camada 0. "
            "O roteador, a auditoria e a memória local já estão ativos."
        )

        return Resposta(
            texto=texto,
            provedor=self.nome,
            modelo="yby-fake",
            custo_usd=0.0,
            tokens_entrada=len(prompt.split()),
            tokens_saida=len(texto.split()),
        )
