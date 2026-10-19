"""Configuração central do YBY SEED.

A configuração é lida de variáveis de ambiente para manter o MVP simples,
sem dependências extras e sem arquivos de configuração obrigatórios.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Configuração imutável do YBY SEED."""

    db_path: Path
    provedor_padrao: str
    modelo_padrao: str
    teto_custo_por_pedido: float
    teto_custo_diario: float
    modo_economia: bool

    @classmethod
    def carregar(cls) -> "Config":
        """Carrega a configuração a partir do ambiente."""

        db_path = Path(
            os.getenv("YBY_DB_PATH", str(Path.home() / ".yby" / "yby.db"))
        )

        return cls(
            db_path=db_path,
            provedor_padrao=os.getenv("YBY_PROVEDOR", "fake"),
            modelo_padrao=os.getenv("YBY_MODELO", "yby-fake"),
            teto_custo_por_pedido=float(os.getenv("YBY_TETO_PEDIDO", "0.50")),
            teto_custo_diario=float(os.getenv("YBY_TETO_DIARIO", "5.00")),
            modo_economia=os.getenv("YBY_MODO_ECONOMIA", "1") == "1",
        )

    def garantir_diretorios(self) -> None:
        """Cria o diretório do banco de dados, se necessário."""

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
