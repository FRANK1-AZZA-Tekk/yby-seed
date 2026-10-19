"""Interface da memória local."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Memoria(ABC):
    """Contrato para memória persistente local."""

    @abstractmethod
    def salvar(self, conteudo: str) -> int:
        """Salva um fato e retorna seu identificador."""

    @abstractmethod
    def buscar(self, consulta: str, limite: int = 5) -> list[str]:
        """Busca fatos relevantes."""
