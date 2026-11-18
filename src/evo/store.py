"""SQLite + FTS5 para eventos Evo (local, offline).

Esquema mínimo compatível com `yby.evo.event.v1` (attrs em JSON sanitizado).
Tabelas futuras (friction/proposals/cycles) ficam fora do v0.1 de código.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.evo.sanitize import sanitize_text, sanitize_value

# Kinds estáveis v0.1 (+ aliases livres mapeados no collect).
EVENT_KINDS = frozenset(
    {
        "command_run",
        "error",
        "test_result",
        "task_completed",
        "user_feedback",
        "skill_use",
        "cloud_call",
    }
)


@dataclass(frozen=True)
class EvoEvent:
    """Evento já pronto para persistir (sanitize no insert)."""

    kind: str
    summary: str
    source: str = ""
    payload: dict[str, Any] | None = None
    severity: str = "info"
    ts: str | None = None  # ISO-8601 UTC; None = now
    ring: int = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def day_from_ts(ts: str) -> str:
    """Extrai YYYY-MM-DD de um timestamp ISO."""

    return ts[:10]


class EvoStore:
    """Persistência local. Cria schema na primeira abertura."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> EvoStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                day TEXT NOT NULL,
                kind TEXT NOT NULL,
                ring INTEGER NOT NULL DEFAULT 1,
                source TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                severity TEXT NOT NULL DEFAULT 'info',
                sanitized INTEGER NOT NULL DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_events_day ON events(day);
            CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);

            CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
                summary,
                payload_json,
                content='events',
                content_rowid='id'
            );

            CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
              INSERT INTO events_fts(rowid, summary, payload_json)
              VALUES (new.id, new.summary, new.payload_json);
            END;
            CREATE TRIGGER IF NOT EXISTS events_ad AFTER DELETE ON events BEGIN
              INSERT INTO events_fts(events_fts, rowid, summary, payload_json)
              VALUES ('delete', old.id, old.summary, old.payload_json);
            END;
            CREATE TRIGGER IF NOT EXISTS events_au AFTER UPDATE ON events BEGIN
              INSERT INTO events_fts(events_fts, rowid, summary, payload_json)
              VALUES ('delete', old.id, old.summary, old.payload_json);
              INSERT INTO events_fts(rowid, summary, payload_json)
              VALUES (new.id, new.summary, new.payload_json);
            END;

            CREATE TABLE IF NOT EXISTS cycles (
                id TEXT PRIMARY KEY,
                day TEXT NOT NULL,
                state TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                report_path TEXT
            );
            """
        )
        self._conn.commit()

    def add_event(self, event: EvoEvent) -> int:
        kind = event.kind.strip()
        if kind not in EVENT_KINDS:
            raise ValueError(f"kind inválido: {kind!r}; use um de {sorted(EVENT_KINDS)}")

        ts = event.ts or _utc_now_iso()
        day = day_from_ts(ts)
        summary = sanitize_text(event.summary)
        source = sanitize_text(event.source or "")
        payload = sanitize_value(event.payload or {})
        if not isinstance(payload, dict):
            payload = {"value": payload}
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        severity = sanitize_text(event.severity or "info")
        ring = int(event.ring) if event.ring is not None else 1

        cur = self._conn.execute(
            """
            INSERT INTO events (
                ts, day, kind, ring, source, summary, payload_json, severity, sanitized
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (ts, day, kind, ring, source, summary, payload_json, severity),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def add_events(self, events: Iterable[EvoEvent]) -> int:
        n = 0
        for event in events:
            self.add_event(event)
            n += 1
        return n

    def events_for_day(self, day: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT id, ts, day, kind, ring, source, summary, payload_json, severity
            FROM events WHERE day = ? ORDER BY ts ASC, id ASC
            """,
            (day,),
        ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def upsert_cycle(
        self,
        cycle_id: str,
        *,
        day: str,
        state: str,
        started_at: str,
        finished_at: str | None = None,
        report_path: str | None = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO cycles (id, day, state, started_at, finished_at, report_path)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              state=excluded.state,
              finished_at=excluded.finished_at,
              report_path=excluded.report_path
            """,
            (cycle_id, day, state, started_at, finished_at, report_path),
        )
        self._conn.commit()

    def search(self, query: str, *, day: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Busca FTS5 (fallback LIKE se FTS falhar)."""

        q = sanitize_text(query.strip())
        if not q:
            return []
        try:
            if day:
                rows = self._conn.execute(
                    """
                    SELECT e.id, e.ts, e.day, e.kind, e.ring, e.source, e.summary,
                           e.payload_json, e.severity
                    FROM events_fts f
                    JOIN events e ON e.id = f.rowid
                    WHERE events_fts MATCH ? AND e.day = ?
                    ORDER BY e.ts ASC
                    LIMIT ?
                    """,
                    (q, day, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """
                    SELECT e.id, e.ts, e.day, e.kind, e.ring, e.source, e.summary,
                           e.payload_json, e.severity
                    FROM events_fts f
                    JOIN events e ON e.id = f.rowid
                    WHERE events_fts MATCH ?
                    ORDER BY e.ts ASC
                    LIMIT ?
                    """,
                    (q, limit),
                ).fetchall()
            return [_row_to_dict(row) for row in rows]
        except sqlite3.OperationalError:
            like = f"%{q}%"
            if day:
                rows = self._conn.execute(
                    """
                    SELECT id, ts, day, kind, ring, source, summary, payload_json, severity
                    FROM events
                    WHERE day = ? AND (summary LIKE ? OR payload_json LIKE ?)
                    ORDER BY ts ASC LIMIT ?
                    """,
                    (day, like, like, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """
                    SELECT id, ts, day, kind, ring, source, summary, payload_json, severity
                    FROM events
                    WHERE summary LIKE ? OR payload_json LIKE ?
                    ORDER BY ts ASC LIMIT ?
                    """,
                    (like, like, limit),
                ).fetchall()
            return [_row_to_dict(row) for row in rows]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    payload_raw = row["payload_json"]
    try:
        payload = json.loads(payload_raw) if payload_raw else {}
    except json.JSONDecodeError:
        payload = {"raw": payload_raw}
    return {
        "id": row["id"],
        "ts": row["ts"],
        "day": row["day"],
        "kind": row["kind"],
        "ring": row["ring"] if "ring" in row.keys() else 1,
        "source": row["source"],
        "summary": row["summary"],
        "payload": payload,
        "severity": row["severity"],
        "schema": "yby.evo.event.v1",
        "sanitized": True,
    }
