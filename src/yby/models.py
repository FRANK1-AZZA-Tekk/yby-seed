"""Modelos de dados da Camada 0."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def agora_iso() -> str:
    """Retorna o momento atual em ISO 8601 UTC."""

    return datetime.now(timezone.utc).isoformat()


@dataclass
class Pedido:
    """Um pedido do usuário em linguagem natural."""

    texto: str
    id: int | None = None
    criado_em: str = field(default_factory=agora_iso)


@dataclass
class Resposta:
    """Resposta gerada por um provedor de IA."""

    texto: str
    provedor: str
    modelo: str
    custo_usd: float = 0.0
    tokens_entrada: int = 0
    tokens_saida: int = 0


@dataclass
class Evento:
    """Registro auditável de uma ação do sistema."""

    pedido_id: int | None
    tipo: str
    provedor: str | None = None
    modelo: str | None = None
    motivo: str | None = None
    custo_usd: float = 0.0
    payload: str = ""
    criado_em: str = field(default_factory=agora_iso)
    id: int | None = None
