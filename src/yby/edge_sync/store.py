"""Persistência vetorial idempotente (PostgreSQL + pgvector e fallback SQLite WAL)."""

from __future__ import annotations

import asyncio
import json
import math
import sqlite3
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from src.yby.edge_sync.schemas import EMBEDDING_DIM, EdgeEvent, StoredEdgeEvent

UpsertStatus = Literal["inserted", "duplicate"]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _format_pgvector(vec: list[float] | None) -> str | None:
    if vec is None:
        return None
    formatted: list[str] = []
    for raw in vec:
        val = float(raw)
        if not math.isfinite(val):
            raise ValueError("embedding contém valor não finito (NaN/Inf)")
        formatted.append(f"{val:.6f}")
    return "[" + ",".join(formatted) + "]"


def _parse_json_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


@runtime_checkable
class VectorEventStore(Protocol):
    backend_name: str

    async def ensure_schema(self) -> None: ...

    async def upsert_event(
        self,
        event: EdgeEvent,
        embedding: list[float] | None,
    ) -> UpsertStatus: ...

    async def count_events(self) -> int: ...

    async def search_similar(
        self,
        query_embedding: list[float],
        *,
        limit: int = 5,
    ) -> list[StoredEdgeEvent]: ...


class PgVectorEdgeStore:
    """Armazenamento idempotente em PostgreSQL + pgvector (`psycopg` assíncrono)."""

    backend_name = "pgvector"

    def __init__(
        self,
        dsn: str,
        *,
        embedding_dim: int = EMBEDDING_DIM,
        connection_factory: Callable[[], Awaitable[Any]] | None = None,
    ) -> None:
        self.dsn = dsn
        self.embedding_dim = embedding_dim
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
                    CREATE TABLE IF NOT EXISTS yby_edge_events (
                        event_id TEXT PRIMARY KEY,
                        device_id TEXT NOT NULL,
                        source_node TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        payload JSONB NOT NULL,
                        text_summary TEXT NOT NULL DEFAULT '',
                        captured_at DOUBLE PRECISION NOT NULL,
                        sensitivity TEXT NOT NULL DEFAULT 'private',
                        embedding vector({int(self.embedding_dim)}),
                        synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            await conn.commit()
        finally:
            await conn.close()

    async def upsert_event(
        self,
        event: EdgeEvent,
        embedding: list[float] | None,
    ) -> UpsertStatus:
        conn = await self._connect()
        try:
            vec_literal = _format_pgvector(embedding)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO yby_edge_events (
                        event_id,
                        device_id,
                        source_node,
                        topic,
                        payload,
                        text_summary,
                        captured_at,
                        sensitivity,
                        embedding
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::vector)
                    ON CONFLICT (event_id) DO NOTHING
                    RETURNING event_id
                    """,
                    (
                        event.event_id,
                        event.device_id,
                        event.source_node,
                        event.topic,
                        json.dumps(event.payload, ensure_ascii=False),
                        event.text_summary,
                        event.captured_at,
                        event.sensitivity,
                        vec_literal,
                    ),
                )
                row = await cur.fetchone()
            await conn.commit()
            return "inserted" if row is not None else "duplicate"
        finally:
            await conn.close()

    async def count_events(self) -> int:
        conn = await self._connect()
        try:
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) FROM yby_edge_events")
                row = await cur.fetchone()
            return int(row[0]) if row else 0
        finally:
            await conn.close()

    async def search_similar(
        self,
        query_embedding: list[float],
        *,
        limit: int = 5,
    ) -> list[StoredEdgeEvent]:
        conn = await self._connect()
        try:
            vec_literal = _format_pgvector(query_embedding)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        event_id,
                        device_id,
                        source_node,
                        topic,
                        payload,
                        captured_at,
                        sensitivity,
                        1.0 - (embedding <=> %s::vector) AS similarity
                    FROM yby_edge_events
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector ASC
                    LIMIT %s
                    """,
                    (vec_literal, vec_literal, max(1, int(limit))),
                )
                rows = await cur.fetchall()
            out: list[StoredEdgeEvent] = []
            for row in rows:
                payload = _parse_json_dict(row[4])
                out.append(
                    StoredEdgeEvent(
                        event_id=str(row[0]),
                        device_id=str(row[1]),
                        source_node=str(row[2]),
                        topic=str(row[3]),
                        payload=payload,
                        captured_at=float(row[5]),
                        sensitivity=row[6],
                        score=float(row[7]) if row[7] is not None else None,
                    )
                )
            return out
        finally:
            await conn.close()


class SQLiteFallbackEdgeStore:
    """Persistência durável local (SQLite WAL) para modo offline ou queda do Postgres."""

    backend_name = "sqlite_fallback"

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_sync()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10.0)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_sync(self) -> None:
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS edge_events_fallback (
                    event_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    source_node TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    text_summary TEXT NOT NULL DEFAULT '',
                    captured_at REAL NOT NULL,
                    sensitivity TEXT NOT NULL DEFAULT 'private',
                    embedding TEXT,
                    drained INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    async def ensure_schema(self) -> None:
        await asyncio.to_thread(self._init_sync)

    def _upsert_sync(self, event: EdgeEvent, embedding: list[float] | None) -> UpsertStatus:
        with self._connection() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO edge_events_fallback (
                    event_id,
                    device_id,
                    source_node,
                    topic,
                    payload,
                    text_summary,
                    captured_at,
                    sensitivity,
                    embedding,
                    drained
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    event.event_id,
                    event.device_id,
                    event.source_node,
                    event.topic,
                    json.dumps(event.payload, ensure_ascii=False),
                    event.text_summary,
                    event.captured_at,
                    event.sensitivity,
                    json.dumps(embedding) if embedding is not None else None,
                ),
            )
            return "inserted" if cur.rowcount == 1 else "duplicate"

    async def upsert_event(
        self,
        event: EdgeEvent,
        embedding: list[float] | None,
    ) -> UpsertStatus:
        return await asyncio.to_thread(self._upsert_sync, event, embedding)

    def _count_sync(self, *, only_undrained: bool = False) -> int:
        query = "SELECT COUNT(*) FROM edge_events_fallback"
        if only_undrained:
            query += " WHERE drained = 0"
        with self._connection() as conn:
            row = conn.execute(query).fetchone()
        return int(row[0]) if row else 0

    async def count_events(self) -> int:
        return await asyncio.to_thread(self._count_sync, only_undrained=False)

    async def count_pending(self) -> int:
        return await asyncio.to_thread(self._count_sync, only_undrained=True)

    def _list_undrained_sync(self, limit: int) -> list[tuple[EdgeEvent, list[float] | None]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    event_id,
                    device_id,
                    source_node,
                    topic,
                    payload,
                    text_summary,
                    captured_at,
                    sensitivity,
                    embedding
                FROM edge_events_fallback
                WHERE drained = 0
                ORDER BY captured_at ASC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()

        items: list[tuple[EdgeEvent, list[float] | None]] = []
        for row in rows:
            emb: list[float] | None = None
            if row[8]:
                try:
                    parsed_emb = json.loads(row[8])
                    if isinstance(parsed_emb, list):
                        emb = parsed_emb
                except (json.JSONDecodeError, TypeError):
                    emb = None
            event = EdgeEvent(
                event_id=str(row[0]),
                device_id=str(row[1]),
                source_node=str(row[2]),
                topic=str(row[3]),
                payload=_parse_json_dict(row[4]),
                text_summary=str(row[5]),
                captured_at=float(row[6]),
                sensitivity=row[7],
                embedding=emb,
            )
            items.append((event, emb))
        return items

    def _mark_drained_sync(self, event_ids: list[str]) -> None:
        if not event_ids:
            return
        with self._connection() as conn:
            conn.executemany(
                "UPDATE edge_events_fallback SET drained = 1 WHERE event_id = ?",
                [(eid,) for eid in event_ids],
            )

    async def drain_to(
        self,
        target: VectorEventStore,
        *,
        batch_size: int = 64,
    ) -> tuple[int, int]:
        """Drena registros pendentes do fallback SQLite para o store primário (pgvector)."""

        pending = await asyncio.to_thread(self._list_undrained_sync, batch_size)
        drained_ids: list[str] = []
        inserted = 0
        duplicates = 0

        try:
            for event, emb in pending:
                status = await target.upsert_event(event, emb)
                if status == "inserted":
                    inserted += 1
                else:
                    duplicates += 1
                drained_ids.append(event.event_id)
        finally:
            if drained_ids:
                await asyncio.to_thread(self._mark_drained_sync, drained_ids)
        return inserted, duplicates

    def _search_sync(self, query_embedding: list[float], limit: int) -> list[StoredEdgeEvent]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    event_id,
                    device_id,
                    source_node,
                    topic,
                    payload,
                    captured_at,
                    sensitivity,
                    embedding
                FROM edge_events_fallback
                WHERE embedding IS NOT NULL
                """
            ).fetchall()

        scored: list[StoredEdgeEvent] = []
        for row in rows:
            try:
                emb = json.loads(row[7])
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(emb, list):
                continue
            score = _cosine_similarity(query_embedding, emb)
            scored.append(
                StoredEdgeEvent(
                    event_id=str(row[0]),
                    device_id=str(row[1]),
                    source_node=str(row[2]),
                    topic=str(row[3]),
                    payload=_parse_json_dict(row[4]),
                    captured_at=float(row[5]),
                    sensitivity=row[6],
                    score=round(score, 6),
                )
            )
        scored.sort(key=lambda item: item.score or 0.0, reverse=True)
        return scored[: max(1, int(limit))]

    async def search_similar(
        self,
        query_embedding: list[float],
        *,
        limit: int = 5,
    ) -> list[StoredEdgeEvent]:
        return await asyncio.to_thread(self._search_sync, query_embedding, limit)
