"""Testes da configuração e do banco local."""

from src.yby.config import Config
from src.yby.db import Banco


def test_config_padrao_usa_provedor_fake(config: Config) -> None:
    assert config.provedor_padrao == "fake"
    assert config.modo_economia is True


def test_banco_cria_tabelas(banco: Banco) -> None:
    pedido_id = banco.criar_pedido("teste", "2026-10-19T00:00:00+00:00")
    assert pedido_id > 0

    eventos = banco.listar_eventos()
    assert eventos == []
