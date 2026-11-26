"""Adapter opcional pgvector (import lazy); se falhar ou sem env -> memória."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from src.yby_machine.embedder import DEFAULT_EMBEDDING_DIM
from src.yby_machine.ports import AppSummary, SpecStorePort, StoredAppRecord
from src.yby_machine.spec import YBYSpec
from src.yby_machine.store import DEFAULT_REUSE_THRESHOLD, InMemorySpecStore


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{float(x):.6f}" for x in vec) + "]"


class PgVectorSpecStore:
    """Persistência opcional em Postgres + pgvector; degrada para memória em erro."""

    def __init__(
        self,
        dsn: str,
        *,
        embedding_dim: int = DEFAULT_EMBEDDING_DIM,
        connection_factory: Callable[[], Awaitable[Any]] | None = None,
        fallback: InMemorySpecStore | None = None,
    ) -> None:
        self.dsn = dsn
        self.embedding_dim = embedding_dim
        self._connection_factory = connection_factory
        self._fallback = fallback or InMemorySpecStore()
        self._schema_ready = False

    async def _connect(self) -> Any:
        if self._connection_factory is not None:
            return await self._connection_factory()
        import psycopg

        return await psycopg.AsyncConnection.connect(self.dsn)

    async def _ensure_schema(self, conn: Any) -> None:
        if self._schema_ready:
            return
        async with conn.cursor() as cur:
            await cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS yby_machine_apps (
                    app_id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    spec_json JSONB NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    embedding vector({int(self.embedding_dim)}) NOT NULL
                )
                """
            )
        await conn.commit()
        self._schema_ready = True

    async def find_similar(
        self,
        embedding: list[float],
        *,
        min_similarity: float = DEFAULT_REUSE_THRESHOLD,
    ) -> StoredAppRecord | None:
        try:
            conn = await self._connect()
            try:
                await self._ensure_schema(conn)
                lit = _vector_literal(embedding)
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT
                            app_id,
                            prompt,
                            spec_json,
                            source,
                            created_at,
                            1.0 - (embedding <=> %s::vector) AS similarity
                        FROM yby_machine_apps
                        ORDER BY embedding <=> %s::vector ASC
                        LIMIT 1
                        """,
                        (lit, lit),
                    )
                    row = await cur.fetchone()
            finally:
                await conn.close()
        except Exception:  # noqa: BLE001
            return await self._fallback.find_similar(embedding, min_similarity=min_similarity)

        if not row:
            return None
        similarity = float(row[5]) if row[5] is not None else 0.0
        if similarity < min_similarity:
            return None
        spec_data = row[2] if isinstance(row[2], dict) else json.loads(str(row[2]))
        return StoredAppRecord(
            app_id=str(row[0]),
            prompt=str(row[1]),
            spec=YBYSpec.model_validate(spec_data),
            source=str(row[3]),
            created_at=str(row[4]),
            similarity=round(similarity, 6),
        )

    async def save(
        self,
        *,
        prompt: str,
        embedding: list[float],
        spec: YBYSpec,
        source: str,
    ) -> StoredAppRecord:
        app_id = uuid.uuid4().hex[:12]
        created_at = datetime.now(timezone.utc).isoformat()
        try:
            conn = await self._connect()
            try:
                await self._ensure_schema(conn)
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO yby_machine_apps (
                            app_id, prompt, spec_json, source, created_at, embedding
                        )
                        VALUES (%s, %s, %s::jsonb, %s, %s, %s::vector)
                        """,
                        (
                            app_id,
                            prompt,
                            json.dumps(spec.model_dump(mode="json"), ensure_ascii=False),
                            source,
                            created_at,
                            _vector_literal(embedding),
                        ),
                    )
                await conn.commit()
            finally:
                await conn.close()
            return StoredAppRecord(
                app_id=app_id,
                prompt=prompt,
                spec=spec,
                source=source,
                created_at=created_at,
            )
        except Exception:  # noqa: BLE001
            return await self._fallback.save(
                prompt=prompt,
                embedding=embedding,
                spec=spec,
                source=source,
            )

    async def list_apps(self, *, limit: int = 50) -> list[AppSummary]:
        try:
            conn = await self._connect()
            try:
                await self._ensure_schema(conn)
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT app_id, spec_json, created_at
                        FROM yby_machine_apps
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (max(1, int(limit)),),
                    )
                    rows = await cur.fetchall()
            finally:
                await conn.close()
            out: list[AppSummary] = []
            for row in rows:
                spec_data = row[1] if isinstance(row[1], dict) else json.loads(str(row[1]))
                spec = YBYSpec.model_validate(spec_data)
                out.append(
                    AppSummary(
                        app_id=str(row[0]),
                        name=spec.name,
                        title=spec.title,
                        description=spec.description,
                        created_at=str(row[2]),
                    )
                )
            return out
        except Exception:  # noqa: BLE001
            return await self._fallback.list_apps(limit=limit)

    async def get_app(self, app_id: str) -> StoredAppRecord | None:
        try:
            conn = await self._connect()
            try:
                await self._ensure_schema(conn)
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT app_id, prompt, spec_json, source, created_at
                        FROM yby_machine_apps
                        WHERE app_id = %s
                        """,
                        (app_id,),
                    )
                    row = await cur.fetchone()
            finally:
                await conn.close()
            if not row:
                return None
            spec_data = row[2] if isinstance(row[2], dict) else json.loads(str(row[2]))
            return StoredAppRecord(
                app_id=str(row[0]),
                prompt=str(row[1]),
                spec=YBYSpec.model_validate(spec_data),
                source=str(row[3]),
                created_at=str(row[4]),
            )
        except Exception:  # noqa: BLE001
            return await self._fallback.get_app(app_id)

    async def close(self) -> None:
        await self._fallback.close()


def create_spec_store_from_env(
    environ: Mapping[str, str] | None = None,
) -> SpecStorePort:
    """Ativa PgVectorSpecStore só com YBY_DATABASE_URL + psycopg importável."""

    source = environ if environ is not None else os.environ
    dsn = source.get("YBY_DATABASE_URL", "").strip()
    if not dsn:
        return InMemorySpecStore()
    try:
        import psycopg  # noqa: F401
    except ImportError:
        return InMemorySpecStore()
    return PgVectorSpecStore(dsn=dsn)
