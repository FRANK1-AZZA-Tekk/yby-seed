"""Armazenamento vetorial híbrido (PostgreSQL + pgvector e fallback em memória)."""

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from src.yby.obsidian_rag.parser import ObsidianChunk
from src.yby_machine.embedder import DEFAULT_EMBEDDING_DIM

_WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÿ_-]+")


class HybridSearchHit(BaseModel):
    """Resultado de busca híbrida (semântica + lexical/metadados)."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    source_path: str
    heading: str
    content: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    wikilinks: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    score: float
    vector_score: float = 0.0
    lexical_score: float = 0.0


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _format_pgvector(vec: list[float]) -> str:
    formatted: list[str] = []
    for raw in vec:
        val = float(raw)
        if not math.isfinite(val):
            raise ValueError("embedding contém valor não finito (NaN/Inf)")
        formatted.append(f"{val:.6f}")
    return "[" + ",".join(formatted) + "]"


def _parse_json(raw: Any, default: Any) -> Any:
    if isinstance(raw, type(default)):
        return raw
    if not raw:
        return default
    try:
        parsed = json.loads(str(raw))
    except (json.JSONDecodeError, TypeError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


def _lexical_score(query: str, chunk: ObsidianChunk) -> float:
    query_tokens = {t.casefold() for t in _WORD_RE.findall(query or "")}
    if not query_tokens:
        return 0.0
    haystack = " ".join(
        [
            chunk.heading,
            chunk.content,
            " ".join(chunk.wikilinks),
            " ".join(chunk.tags),
            json.dumps(chunk.frontmatter, ensure_ascii=False),
        ]
    )
    doc_tokens = {t.casefold() for t in _WORD_RE.findall(haystack)}
    if not doc_tokens:
        return 0.0
    matched = len(query_tokens & doc_tokens)
    return matched / len(query_tokens)


@runtime_checkable
class ObsidianChunkStore(Protocol):
    backend_name: str

    async def ensure_schema(self) -> None: ...

    async def upsert_chunks(
        self,
        chunks: list[ObsidianChunk],
        embeddings: list[list[float]],
    ) -> int: ...

    async def delete_by_source(self, source_path: str) -> int: ...

    async def count_chunks(self) -> int: ...

    async def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        *,
        limit: int = 5,
        wikilink: str | None = None,
        tag: str | None = None,
    ) -> list[HybridSearchHit]: ...


class InMemoryObsidianStore:
    """Fallback 100% offline em memória com ranking híbrido (vetor + léxico/metadados)."""

    backend_name = "memory"

    def __init__(self) -> None:
        self._items: dict[str, tuple[ObsidianChunk, list[float]]] = {}

    async def ensure_schema(self) -> None:
        return None

    async def upsert_chunks(
        self,
        chunks: list[ObsidianChunk],
        embeddings: list[list[float]],
    ) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks e embeddings devem ter o mesmo tamanho")
        for chunk, vec in zip(chunks, embeddings, strict=True):
            self._items[chunk.chunk_id] = (chunk, list(vec))
        return len(chunks)

    async def delete_by_source(self, source_path: str) -> int:
        to_delete = [
            cid for cid, (chunk, _vec) in self._items.items() if chunk.source_path == source_path
        ]
        for cid in to_delete:
            del self._items[cid]
        return len(to_delete)

    async def count_chunks(self) -> int:
        return len(self._items)

    async def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        *,
        limit: int = 5,
        wikilink: str | None = None,
        tag: str | None = None,
    ) -> list[HybridSearchHit]:
        link_filter = wikilink.strip().casefold() if wikilink else None
        tag_filter = tag.strip().lstrip("#").casefold() if tag else None

        hits: list[HybridSearchHit] = []
        for chunk, vec in self._items.values():
            if link_filter and not any(w.casefold() == link_filter for w in chunk.wikilinks):
                continue
            if tag_filter and not any(t.casefold() == tag_filter for t in chunk.tags):
                continue

            vec_score = max(0.0, _cosine_similarity(query_embedding, vec))
            lex_score = _lexical_score(query, chunk)
            combined = 0.7 * vec_score + 0.3 * lex_score
            hits.append(
                HybridSearchHit(
                    chunk_id=chunk.chunk_id,
                    source_path=chunk.source_path,
                    heading=chunk.heading,
                    content=chunk.content,
                    frontmatter=chunk.frontmatter,
                    wikilinks=chunk.wikilinks,
                    tags=chunk.tags,
                    score=round(combined, 6),
                    vector_score=round(vec_score, 6),
                    lexical_score=round(lex_score, 6),
                )
            )

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[: max(1, int(limit))]


class PgVectorObsidianStore:
    """Persistência híbrida em PostgreSQL + pgvector + FTS (`psycopg` lazy)."""

    backend_name = "pgvector"

    def __init__(
        self,
        dsn: str,
        *,
        embedding_dim: int = DEFAULT_EMBEDDING_DIM,
        connection_factory: Callable[[], Awaitable[Any]] | None = None,
    ) -> None:
        self.dsn = dsn
        self.embedding_dim = int(embedding_dim)
        self._connection_factory = connection_factory

    async def _connect(self) -> Any:
        if self._connection_factory is not None:
            return await self._connection_factory()
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "Dependência opcional 'psycopg' não instalada. "
                "Instale com `uv sync --extra mesh` ou `pip install -r requirements-mesh.txt`."
            ) from exc
        return await psycopg.AsyncConnection.connect(self.dsn)

    async def ensure_schema(self) -> None:
        conn = await self._connect()
        try:
            async with conn.cursor() as cur:
                await cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                await cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS yby_obsidian_chunks (
                        chunk_id TEXT PRIMARY KEY,
                        source_path TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        heading TEXT NOT NULL DEFAULT '',
                        content TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        frontmatter JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        wikilinks JSONB NOT NULL DEFAULT '[]'::jsonb,
                        tags JSONB NOT NULL DEFAULT '[]'::jsonb,
                        embedding vector({self.embedding_dim}) NOT NULL,
                        search_tsv tsvector GENERATED ALWAYS AS (
                            to_tsvector('portuguese', coalesce(heading, '') || ' ' || content)
                        ) STORED,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            await conn.commit()
        finally:
            await conn.close()

    async def upsert_chunks(
        self,
        chunks: list[ObsidianChunk],
        embeddings: list[list[float]],
    ) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks e embeddings devem ter o mesmo tamanho")
        if not chunks:
            return 0
        conn = await self._connect()
        try:
            async with conn.cursor() as cur:
                for chunk, vec in zip(chunks, embeddings, strict=True):
                    await cur.execute(
                        """
                        INSERT INTO yby_obsidian_chunks (
                            chunk_id,
                            source_path,
                            chunk_index,
                            heading,
                            content,
                            content_hash,
                            frontmatter,
                            wikilinks,
                            tags,
                            embedding
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::vector)
                        ON CONFLICT (chunk_id) DO UPDATE SET
                            heading = EXCLUDED.heading,
                            content = EXCLUDED.content,
                            content_hash = EXCLUDED.content_hash,
                            frontmatter = EXCLUDED.frontmatter,
                            wikilinks = EXCLUDED.wikilinks,
                            tags = EXCLUDED.tags,
                            embedding = EXCLUDED.embedding,
                            updated_at = NOW()
                        """,
                        (
                            chunk.chunk_id,
                            chunk.source_path,
                            chunk.chunk_index,
                            chunk.heading,
                            chunk.content,
                            chunk.content_hash,
                            json.dumps(chunk.frontmatter, ensure_ascii=False),
                            json.dumps(chunk.wikilinks, ensure_ascii=False),
                            json.dumps(chunk.tags, ensure_ascii=False),
                            _format_pgvector(vec),
                        ),
                    )
            await conn.commit()
            return len(chunks)
        finally:
            await conn.close()

    async def delete_by_source(self, source_path: str) -> int:
        conn = await self._connect()
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM yby_obsidian_chunks WHERE source_path = %s",
                    (source_path,),
                )
                deleted = int(getattr(cur, "rowcount", 0) or 0)
            await conn.commit()
            return deleted
        finally:
            await conn.close()

    async def count_chunks(self) -> int:
        conn = await self._connect()
        try:
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) FROM yby_obsidian_chunks")
                row = await cur.fetchone()
            return int(row[0]) if row else 0
        finally:
            await conn.close()

    async def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        *,
        limit: int = 5,
        wikilink: str | None = None,
        tag: str | None = None,
    ) -> list[HybridSearchHit]:
        conn = await self._connect()
        try:
            vec_literal = _format_pgvector(query_embedding)
            where_clauses = ["TRUE"]
            params: list[Any] = [vec_literal, query, vec_literal, query]

            if wikilink:
                where_clauses.append("wikilinks @> %s::jsonb")
                params.append(json.dumps([wikilink.strip()], ensure_ascii=False))
            if tag:
                where_clauses.append("tags @> %s::jsonb")
                params.append(json.dumps([tag.strip().lstrip("#").casefold()], ensure_ascii=False))

            params.append(max(1, int(limit)))
            where_sql = " AND ".join(where_clauses)

            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    SELECT
                        chunk_id,
                        source_path,
                        heading,
                        content,
                        frontmatter,
                        wikilinks,
                        tags,
                        (1.0 - (embedding <=> %s::vector)) AS vector_score,
                        ts_rank(search_tsv, plainto_tsquery('portuguese', %s)) AS lexical_score,
                        (
                            0.7 * (1.0 - (embedding <=> %s::vector))
                            + 0.3 * ts_rank(search_tsv, plainto_tsquery('portuguese', %s))
                        ) AS hybrid_score
                    FROM yby_obsidian_chunks
                    WHERE {where_sql}
                    ORDER BY hybrid_score DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                rows = await cur.fetchall()

            hits: list[HybridSearchHit] = []
            for row in rows:
                hits.append(
                    HybridSearchHit(
                        chunk_id=str(row[0]),
                        source_path=str(row[1]),
                        heading=str(row[2]),
                        content=str(row[3]),
                        frontmatter=_parse_json(row[4], {}),
                        wikilinks=_parse_json(row[5], []),
                        tags=_parse_json(row[6], []),
                        vector_score=round(float(row[7] or 0.0), 6),
                        lexical_score=round(float(row[8] or 0.0), 6),
                        score=round(float(row[9] or 0.0), 6),
                    )
                )
            return hits
        finally:
            await conn.close()


def create_obsidian_store_from_env(
    environ: Mapping[str, str] | None = None,
    *,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
) -> ObsidianChunkStore:
    """Ativa PgVectorObsidianStore só quando DSN estiver configurado e `psycopg` importável."""

    source = environ if environ is not None else os.environ
    dsn = (
        source.get("YBY_PGVECTOR_DSN")
        or source.get("YBY_DATABASE_URL")
        or ""
    ).strip()
    if not dsn:
        return InMemoryObsidianStore()
    try:
        import psycopg  # noqa: F401
    except ImportError:
        return InMemoryObsidianStore()
    return PgVectorObsidianStore(dsn=dsn, embedding_dim=embedding_dim)
