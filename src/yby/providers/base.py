"""Interface base dos provedores de IA."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Config
from ..models import Resposta


class Provedor(ABC):
    """Contrato comum para modelos locais, fake e na nuvem."""

    def __init__(self, config: Config) -> None:
        self.config = config

    @property
    @abstractmethod
    def nome(self) -> str:
        """Nome curto do provedor."""

    @abstractmethod
    def gerar(self, prompt: str) -> Resposta:
        """Gera uma resposta a partir de um prompt."""
