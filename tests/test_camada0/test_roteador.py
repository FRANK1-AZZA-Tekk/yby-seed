"""Testes do roteador, custo e provedor fake."""

import pytest

from src.yby.config import Config
from src.yby.core.roteador import Roteador
from src.yby.models import Resposta


def test_provedor_fake_gera_resposta(config: Config) -> None:
    roteador = Roteador(config)
    resposta = roteador.resolver_provedor().gerar("oi")

    assert resposta.provedor == "fake"
    assert resposta.custo_usd == 0.0
    assert "Camada 0" in resposta.texto


def test_modo_economia_bloqueia_openrouter(config: Config) -> None:
    roteador = Roteador(config)
    provedor = roteador.resolver_provedor("openrouter")

    assert provedor.nome == "fake"


def test_teto_de_custo_bloqueia_resposta(config: Config) -> None:
    config = Config(
        db_path=config.db_path,
        provedor_padrao="fake",
        modelo_padrao="yby-fake",
        teto_custo_por_pedido=0.0,
        teto_custo_diario=5.0,
        modo_economia=False,
    )

    roteador = Roteador(config)
    resposta = Resposta(
        texto="teste",
        provedor="fake",
        modelo="yby-fake",
        custo_usd=0.01,
    )

    with pytest.raises(ValueError):
        roteador.validar_custo(resposta)
