"""Banco SQLite local do YBY SEED."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import Config


SCHEMA = """
CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    texto TEXT NOT NULL,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER REFERENCES pedidos(id),
    tipo TEXT NOT NULL,
    provedor TEXT,
    modelo TEXT,
    motivo TEXT,
    custo_usd REAL NOT NULL DEFAULT 0,
    payload TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conteudo TEXT NOT NULL,
    criado_em TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS memorias_busca USING fts5(
    conteudo,
    content='memorias',
    content_rowid='id'
);
"""


class Banco:
    """Conexão SQLite com esquema inicial do YBY SEED."""

    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.conexao = sqlite3.connect(self.caminho)
        self.conexao.row_factory = sqlite3.Row
        self.conexao.executescript(SCHEMA)
        self.conexao.commit()

    def fechar(self) -> None:
        self.conexao.close()

    def criar_pedido(self, texto: str, criado_em: str) -> int:
        cursor = self.conexao.execute(
            "INSERT INTO pedidos (texto, criado_em) VALUES (?, ?)",
            (texto, criado_em),
        )
        self.conexao.commit()
        return int(cursor.lastrowid)

    def criar_evento(
        self,
        pedido_id: int | None,
        tipo: str,
        provedor: str | None,
        modelo: str | None,
        motivo: str | None,
        custo_usd: float,
        payload: str,
        criado_em: str,
    ) -> int:
        cursor = self.conexao.execute(
            """
            INSERT INTO eventos
                (pedido_id, tipo, provedor, modelo, motivo, custo_usd, payload, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (pedido_id, tipo, provedor, modelo, motivo, custo_usd, payload, criado_em),
        )
        self.conexao.commit()
        return int(cursor.lastrowid)

    def listar_eventos(self) -> list[sqlite3.Row]:
        return list(
            self.conexao.execute(
                "SELECT * FROM eventos ORDER BY id DESC LIMIT 100"
            )
        )
