"""Auditoria append-only do YBY SEED."""

from __future__ import annotations

from ..db import Banco
from ..models import Evento


class Auditoria:
    """Registra eventos sem alterar ou apagar registros anteriores."""

    def __init__(self, banco: Banco) -> None:
        self.banco = banco

    def registrar(self, evento: Evento) -> int:
        """Grava um evento e retorna o identificador criado."""

        return self.banco.criar_evento(
            pedido_id=evento.pedido_id,
            tipo=evento.tipo,
            provedor=evento.provedor,
            modelo=evento.modelo,
            motivo=evento.motivo,
            custo_usd=evento.custo_usd,
            payload=evento.payload,
            criado_em=evento.criado_em,
        )
