"""Recuperação assíncrona de contexto técnico (pgvector + LiteLLM embeddings)."""

from __future__ import annotations

import asyncio
import os
from functools import partial

import psycopg
from openai import OpenAI

from src.yby_seed.config import get_settings

EMBED_MODEL = "nomic-embed-text"


def _database_url() -> str:
    dsn = os.environ.get("YBY_DATABASE_URL", "").strip()
    if dsn:
        return dsn
    password = os.environ.get("POSTGRES_PASSWORD", "yby_local_dev")
    return f"postgresql://yby:{password}@127.0.0.1:5432/yby_brain"


def _fetch_sync(query: str, domain: str | None, top_k: int) -> str:
    settings = get_settings()
    client = OpenAI(base_url=settings.litellm_base_url, api_key=settings.litellm_api_key)
    vector = client.embeddings.create(model=EMBED_MODEL, input=query).data[0].embedding

    sql = """
        SELECT content, domain, source_file
        FROM knowledge_chunks
        WHERE (%s::text IS NULL OR domain = %s)
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    lines: list[str] = []
    try:
        with psycopg.connect(_database_url()) as conn:
            rows = conn.execute(sql, (domain, domain, vector, top_k)).fetchall()
    except Exception:
        return ""

    for content, dom, source in rows:
        header = f"[{dom}:{source}]"
        lines.append(f"{header}\n{content}")
    return "\n\n---\n\n".join(lines)


async def fetch_context(query: str, domain: str | None = None, top_k: int = 4) -> str:
    """Busca trechos relevantes para injeção no prompt do engine."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_fetch_sync, query, domain, top_k))
