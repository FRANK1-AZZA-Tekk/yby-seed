"""Testes do roteador, custo e provedor fake."""

import pytest

from src.yby.config import Config
from src.yby.core.roteador import Roteador
from src.yby.models import Resposta


DIA = "2026-10-19T12:00:00+00:00"


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

    with pytest.raises(ValueError, match="excede o teto"):
        roteador.validar_custo(resposta)


def test_estimativa_acima_do_teto_bloqueia_antes_da_chamada(config: Config) -> None:
    roteador = Roteador(config)

    with pytest.raises(ValueError, match="excede o teto"):
        roteador.validar_custo_previsto(0.51, DIA)


def test_estimativa_abaixo_do_teto_e_permitida(config: Config) -> None:
    roteador = Roteador(config)

    roteador.validar_custo_previsto(0.49, DIA)


@pytest.mark.parametrize("valor", [-0.01, float("nan"), float("inf")])
def test_custos_invalidos_sao_rejeitados(config: Config, valor: float) -> None:
    roteador = Roteador(config)

    with pytest.raises(ValueError, match="Custo inválido"):
        roteador.validar_custo_previsto(valor, DIA)

    resposta = Resposta(
        texto="teste",
        provedor="fake",
        modelo="yby-fake",
        custo_usd=valor,
    )

    with pytest.raises(ValueError, match="Custo inválido"):
        roteador.validar_custo(resposta)


def test_teto_diario_bloqueia_quando_gasto_mais_estimativa_excede_limite(
    config: Config,
) -> None:
    from src.yby.db import Banco

    banco = Banco(config.db_path)
    roteador = Roteador(config, banco)

    banco.criar_evento(
        pedido_id=None,
        tipo="resposta_gerada",
        provedor="fake",
        modelo="yby-fake",
        motivo="Teste",
        custo_usd=4.80,
        payload="",
        criado_em=DIA,
    )

    with pytest.raises(ValueError, match="Teto diário atingido"):
        roteador.validar_custo_previsto(0.30, DIA)

    banco.fechar()


def test_teto_diario_permite_gasto_abaixo_do_limite(config: Config) -> None:
    from src.yby.db import Banco

    banco = Banco(config.db_path)
    roteador = Roteador(config, banco)

    banco.criar_evento(
        pedido_id=None,
        tipo="resposta_gerada",
        provedor="fake",
        modelo="yby-fake",
        motivo="Teste",
        custo_usd=4.80,
        payload="",
        criado_em=DIA,
    )

    roteador.validar_custo_previsto(0.10, DIA)

    banco.fechar()


def test_teto_diario_nao_conta_gasto_de_outro_dia(config: Config) -> None:
    from src.yby.db import Banco

    banco = Banco(config.db_path)
    roteador = Roteador(config, banco)

    banco.criar_evento(
        pedido_id=None,
        tipo="resposta_gerada",
        provedor="fake",
        modelo="yby-fake",
        motivo="Teste",
        custo_usd=4.80,
        payload="",
        criado_em="2026-10-18T12:00:00+00:00",
    )

    roteador.validar_custo_previsto(4.90, DIA)

    banco.fechar()


def test_teto_diario_nao_conta_eventos_de_erro(config: Config) -> None:
    from src.yby.db import Banco

    banco = Banco(config.db_path)
    roteador = Roteador(config, banco)

    banco.criar_evento(
        pedido_id=None,
        tipo="erro",
        provedor="fake",
        modelo="yby-fake",
        motivo="Teste",
        custo_usd=4.80,
        payload="",
        criado_em=DIA,
    )

    roteador.validar_custo_previsto(4.90, DIA)

    banco.fechar()
