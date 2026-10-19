"""Provedor OpenRouter — implementação entra na Camada 1."""

from __future__ import annotations

from ..messages import PROVEDOR_NAO_IMPLEMENTADO
from ..models import Resposta
from .base import Provedor


class ProvedorOpenRouter(Provedor):
    """Reservado para integração com OpenRouter na Camada 1."""

    @property
    def nome(self) -> str:
        return "openrouter"

    def gerar(self, prompt: str) -> Resposta:
        raise NotImplementedError(
            PROVEDOR_NAO_IMPLEMENTADO.format(provedor=self.nome)
        )
