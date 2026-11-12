"""Recuperação assíncrona de contexto técnico (pgvector + LiteLLM embeddings)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from psycopg import AsyncConnection

from src.yby_seed.config import Settings, get_settings
from src.yby_seed.runtime import resources

logger = logging.getLogger(__name__)

EMBED_MODEL = "nomic-embed-text"

_SQL = """
    SELECT content, domain, source_file
    FROM knowledge_chunks
    WHERE (%s::text IS NULL OR domain = %s)
    ORDER BY embedding <=> %s::vector
    LIMIT %s
"""


def _embed_query(query: str, settings: Settings) -> list[float]:
    client = resources.build_openai_client(settings)
    response = client.embeddings.create(model=EMBED_MODEL, input=query)
    return response.data[0].embedding


def _format_rows(rows: list[tuple[Any, ...]]) -> str:
    lines: list[str] = []
    for content, dom, source in rows:
        header = f"[{dom}:{source}]"
        lines.append(f"{header}\n{content}")
    return "\n\n---\n\n".join(lines)


async def _query_vectors(
    conn: AsyncConnection,
    domain: str | None,
    vector: list[float],
    top_k: int,
) -> list[tuple[Any, ...]]:
    async with conn.cursor() as cur:
        await cur.execute(_SQL, (domain, domain, vector, top_k))
        return await cur.fetchall()


async def fetch_context(query: str, domain: str | None = None, top_k: int = 4) -> str:
    """Busca trechos relevantes para injeção no prompt do engine."""
    settings = get_settings()
    try:
        vector = await asyncio.to_thread(_embed_query, query, settings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("embedding indisponível: %s", exc)
        return ""

    pool = resources.get_pg_pool()
    try:
        if pool is not None:
            async with pool.connection() as conn:
                rows = await _query_vectors(conn, domain, vector, top_k)
        else:
            dsn = resources.database_url(settings)
            async with await AsyncConnection.connect(dsn) as conn:
                rows = await _query_vectors(conn, domain, vector, top_k)
    except Exception as exc:  # noqa: BLE001
        logger.warning("consulta pgvector falhou: %s", exc)
        return ""

    return _format_rows(rows)
