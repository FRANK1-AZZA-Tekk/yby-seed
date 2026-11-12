"""Recuperação assíncrona de contexto técnico (pgvector + FTS + RRF)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from psycopg import AsyncConnection

from src.yby_seed.config import Settings, get_settings
from src.yby_seed.runtime import resources
from src.yby_seed.runtime.gpu_sync import sync_inference_slot

logger = logging.getLogger(__name__)

EMBED_MODEL = "nomic-embed-text"
RRF_K = 60

_SQL_VECTOR = """
    SELECT content, domain, source_file
    FROM knowledge_chunks
    WHERE (%s::text IS NULL OR domain = %s)
    ORDER BY embedding <=> %s::vector
    LIMIT %s
"""

_SQL_FTS = """
    SELECT content, domain, source_file
    FROM knowledge_chunks
    WHERE (%s::text IS NULL OR domain = %s)
      AND tsv @@ plainto_tsquery('simple', %s)
    ORDER BY ts_rank_cd(tsv, plainto_tsquery('simple', %s)) DESC
    LIMIT %s
"""


def rrf_score(vec_rank: int | None, fts_rank: int | None, k: int = RRF_K) -> float:
    score = 0.0
    if vec_rank is not None:
        score += 1.0 / (k + vec_rank)
    if fts_rank is not None:
        score += 1.0 / (k + fts_rank)
    return score


def fuse_rrf(
    vec_rows: list[tuple[Any, ...]],
    fts_rows: list[tuple[Any, ...]],
    top_k: int,
    k: int = RRF_K,
) -> list[tuple[Any, ...]]:
    """Funde rankings vetorial e lexical com Reciprocal Rank Fusion."""
    keys: dict[tuple[str, str, str], dict[str, Any]] = {}

    def _key(row: tuple[Any, ...]) -> tuple[str, str, str]:
        content, dom, source = row[0], row[1], row[2]
        return (str(content), str(dom), str(source))

    for rank, row in enumerate(vec_rows, start=0):
        entry = keys.setdefault(_key(row), {"row": row, "vec": None, "fts": None})
        entry["vec"] = rank
    for rank, row in enumerate(fts_rows, start=0):
        entry = keys.setdefault(_key(row), {"row": row, "vec": None, "fts": None})
        entry["fts"] = rank

    scored: list[tuple[float, tuple[Any, ...]]] = []
    for entry in keys.values():
        score = rrf_score(entry["vec"], entry["fts"], k=k)
        scored.append((score, entry["row"]))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _score, row in scored[:top_k]]


def _embed_query(query: str, settings: Settings) -> list[float]:
    client = resources.build_openai_client(settings)
    with sync_inference_slot():
        response = client.embeddings.create(model=EMBED_MODEL, input=query)
    return response.data[0].embedding


def _format_rows(rows: list[tuple[Any, ...]]) -> str:
    lines: list[str] = []
    for content, dom, source in rows:
        header = f"[{dom}:{source}]"
        lines.append(f"{header}\n{content}")
    return "\n\n---\n\n".join(lines)


async def _query(
    conn: AsyncConnection,
    sql: str,
    params: tuple[Any, ...],
) -> list[tuple[Any, ...]]:
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def _hybrid_query(
    conn: AsyncConnection,
    domain: str | None,
    query: str,
    vector: list[float],
    top_k: int,
) -> list[tuple[Any, ...]]:
    vec_limit = max(top_k * 3, top_k)
    vec_rows = await _query(conn, _SQL_VECTOR, (domain, domain, vector, vec_limit))
    try:
        fts_rows = await _query(conn, _SQL_FTS, (domain, domain, query, query, vec_limit))
    except Exception as exc:  # noqa: BLE001
        logger.debug("FTS indisponível (coluna tsv?): %s", exc)
        fts_rows = []
    if not fts_rows:
        return vec_rows[:top_k]
    return fuse_rrf(vec_rows, fts_rows, top_k)


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
                rows = await _hybrid_query(conn, domain, query, vector, top_k)
        else:
            dsn = resources.database_url(settings)
            async with await AsyncConnection.connect(dsn) as conn:
                rows = await _hybrid_query(conn, domain, query, vector, top_k)
    except Exception as exc:  # noqa: BLE001
        logger.warning("consulta híbrida falhou: %s", exc)
        return ""

    return _format_rows(rows)
