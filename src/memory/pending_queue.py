"""Fila local de episódios quando Mem0/Supabase está indisponível (stdlib sqlite3)."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PendingEpisode:
    id: int
    source_id: str
    payload: dict[str, Any]
    created_at: float
    attempts: int


class PendingEpisodeQueue:
    """Persistência em SQLite; sem dependências novas."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_schema()

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at REAL NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.commit()

    def enqueue(self, source_id: str, payload: dict[str, Any], *, now: float | None = None) -> int:
        stamp = time.time() if now is None else now
        body = json.dumps(payload, ensure_ascii=False)
        cur = self._conn.execute(
            "INSERT INTO pending_episodes (source_id, payload, created_at, attempts) VALUES (?, ?, ?, 0)",
            (source_id, body, stamp),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def pending_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM pending_episodes").fetchone()
        return int(row[0]) if row else 0

    def list_batch(self, limit: int = 32) -> list[PendingEpisode]:
        rows = self._conn.execute(
            "SELECT id, source_id, payload, created_at, attempts FROM pending_episodes "
            "ORDER BY id ASC LIMIT ?",
            (limit,),
        ).fetchall()
        out: list[PendingEpisode] = []
        for row in rows:
            payload = json.loads(row[2])
            if not isinstance(payload, dict):
                continue
            out.append(
                PendingEpisode(
                    id=int(row[0]),
                    source_id=str(row[1]),
                    payload=payload,
                    created_at=float(row[3]),
                    attempts=int(row[4]),
                )
            )
        return out

    def mark_attempt(self, episode_id: int) -> None:
        self._conn.execute(
            "UPDATE pending_episodes SET attempts = attempts + 1 WHERE id = ?",
            (episode_id,),
        )
        self._conn.commit()

    def remove(self, episode_id: int) -> None:
        self._conn.execute("DELETE FROM pending_episodes WHERE id = ?", (episode_id,))
        self._conn.commit()