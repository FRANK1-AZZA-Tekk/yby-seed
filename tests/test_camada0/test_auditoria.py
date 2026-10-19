"""Testes da auditoria append-only."""

from src.yby.core.auditoria import Auditoria
from src.yby.models import Evento


def test_registra_evento(banco) -> None:
    auditoria = Auditoria(banco)
    pedido_id = banco.criar_pedido("oi", "2026-10-19T00:00:00+00:00")

    evento_id = auditoria.registrar(
        Evento(
            pedido_id=pedido_id,
            tipo="pedido_recebido",
            motivo="Teste",
            payload="oi",
        )
    )

    assert evento_id > 0
    assert len(banco.listar_eventos()) == 1
