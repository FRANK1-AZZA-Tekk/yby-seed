"""Fixtures dos testes da Camada 0."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.yby.config import Config
from src.yby.db import Banco


@pytest.fixture()
def config(tmp_path: Path) -> Config:
    return Config(
        db_path=tmp_path / "yby-test.db",
        provedor_padrao="fake",
        modelo_padrao="yby-fake",
        teto_custo_por_pedido=0.50,
        teto_custo_diario=5.00,
        modo_economia=True,
    )


@pytest.fixture()
def banco(config: Config) -> Banco:
    instancia = Banco(config.db_path)
    yield instancia
    instancia.fechar()
