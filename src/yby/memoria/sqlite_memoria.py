"""Memória local em SQLite com busca textual FTS5."""

from __future__ import annotations

from ..db import Banco
from ..models import agora_iso
from .base import Memoria


class MemoriaSQLite(Memoria):
    """Memória local, auditável e sem envio de dados para a nuvem."""

    def __init__(self, banco: Banco) -> None:
        self.banco = banco

    def salvar(self, conteudo: str) -> int:
        cursor = self.banco.conexao.execute(
            "INSERT INTO memorias (conteudo, criado_em) VALUES (?, ?)",
            (conteudo, agora_iso()),
        )
        self.banco.conexao.commit()
        return int(cursor.lastrowid)

    def buscar(self, consulta: str, limite: int = 5) -> list[str]:
        resultado = self.banco.conexao.execute(
            """
            SELECT m.conteudo
            FROM memorias_busca b
            JOIN memorias m ON m.id = b.rowid
            WHERE memorias_busca MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (consulta, limite),
        )
        return [linha["conteudo"] for linha in resultado]
