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
    assert Roteador(config).resolver_provedor("openrouter").nome == "fake"


def test_teto_de_custo_bloqueia_resposta(config: Config) -> None:
    config = Config(
        db_path=config.db_path,
        provedor_padrao="fake",
        modelo_padrao="yby-fake",
        teto_custo_por_pedido=0.0,
        teto_custo_diario=5.0,
        modo_economia=False,
    )
    resposta = Resposta(
        texto="teste", provedor="fake", modelo="yby-fake", custo_usd=0.01
    )
    with pytest.raises(ValueError, match="excede o teto"):
        Roteador(config).validar_custo(resposta)


def test_estimativa_acima_do_teto_bloqueia_antes_da_chamada(config: Config) -> None:
    with pytest.raises(ValueError, match="excede o teto"):
        Roteador(config).validar_custo_previsto(0.51)


def test_estimativa_abaixo_do_teto_e_permitida(config: Config) -> None:
    Roteador(config).validar_custo_previsto(0.49)


@pytest.mark.parametrize("valor", [-0.01, float("nan"), float("inf")])
def test_custos_invalidos_sao_rejeitados(config: Config, valor: float) -> None:
    roteador = Roteador(config)
    with pytest.raises(ValueError, match="Custo inválido"):
        roteador.validar_custo_previsto(valor)
    resposta = Resposta(
        texto="teste", provedor="fake", modelo="yby-fake", custo_usd=valor
    )
    with pytest.raises(ValueError, match="Custo inválido"):
        roteador.validar_custo(resposta)
