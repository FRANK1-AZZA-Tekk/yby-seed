"""Registry SQLite local de uso de nuvem (CLOUD_USAGE_SPEC S1 / #42).

Sem ORM. stdlib sqlite3 + WAL. Segredos nunca são persistidos.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = "logs/cloud_usage.sqlite3"

FORBIDDEN_KEYS = frozenset({"prompt", "api_key", "response", "text", "audio"})

# legacy result → status canônico (§4.3)
_RESULT_TO_STATUS: dict[str, str] = {
    "cloud_requested": "requested",
    "cloud_confirmed": "confirmed",
    "cloud_completed": "completed",
    "cloud_failed": "failed",
    "cloud_cancelled": "cancelled",
    "cloud_blocked_local_only": "blocked_local_only",
    "cloud_blocked_budget": "blocked_budget",
    "cloud_blocked_no_tty": "blocked_no_tty",
    "cloud_blocked_authz": "blocked_authz",
    "cloud_exception_granted": "exception_granted",
}

_STATUS_TO_RESULT: dict[str, str] = {v: k for k, v in _RESULT_TO_STATUS.items()}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cloud_usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    purpose TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd REAL,
    status TEXT NOT NULL,
    session_id TEXT,
    task_id TEXT,
    prompt_hash TEXT,
    prompt_ref TEXT,
    result_ref TEXT,
    result TEXT,
    error_code TEXT,
    meta_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_cloud_usage_ts ON cloud_usage_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_cloud_usage_status_ts
    ON cloud_usage_events(status, timestamp);
CREATE INDEX IF NOT EXISTS idx_cloud_usage_session ON cloud_usage_events(session_id);
CREATE INDEX IF NOT EXISTS idx_cloud_usage_provider_model_ts
    ON cloud_usage_events(provider, model, timestamp);
"""


@dataclass(frozen=True)
class ImportReport:
    imported_n: int
    skipped_n: int
    last_timestamp: float | None


@dataclass(frozen=True)
class UsageTotals:
    day_tokens: int
    month_tokens: int
    day_cost_usd: float
    month_cost_usd: float


class CloudUsageRegistry:
    """Persistência SQLite de eventos de nuvem (metadados apenas)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None
        self._imported_once = False

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> CloudUsageRegistry:
        source = environ if environ is not None else os.environ
        raw = source.get("YBY_CLOUD_DB_PATH", DEFAULT_DB_PATH).strip() or DEFAULT_DB_PATH
        return cls(Path(raw))

    def open(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.parent.chmod(0o700)
        except OSError:
            pass
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(_SCHEMA)
        conn.commit()
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
        self._conn = conn
        return conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def count_events(self) -> int:
        conn = self.open()
        row = conn.execute("SELECT COUNT(*) FROM cloud_usage_events").fetchone()
        return int(row[0]) if row else 0

    def insert_event(self, event: dict[str, Any]) -> int:
        """Insere um evento (dict estilo JSONL ou com status canônico)."""

        for key in FORBIDDEN_KEYS:
            if key in event:
                raise ValueError(f"campo proibido no registry: {key}")

        row = _normalize_event(event)
        conn = self.open()
        cur = conn.execute(
            """
            INSERT INTO cloud_usage_events (
                timestamp, provider, model, purpose,
                input_tokens, output_tokens, estimated_cost_usd,
                status, session_id, task_id, prompt_hash, prompt_ref,
                result_ref, result, error_code, meta_json
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            """,
            (
                row["timestamp"],
                row["provider"],
                row["model"],
                row["purpose"],
                row["input_tokens"],
                row["output_tokens"],
                row["estimated_cost_usd"],
                row["status"],
                row["session_id"],
                row["task_id"],
                row["prompt_hash"],
                row["prompt_ref"],
                row["result_ref"],
                row["result"],
                row["error_code"],
                row["meta_json"],
            ),
        )
        conn.commit()
        return int(cur.lastrowid)

    def import_jsonl(self, path: Path) -> ImportReport:
        """Import one-shot de linhas JSONL válidas."""

        if not path.is_file():
            return ImportReport(0, 0, None)
        imported = 0
        skipped = 0
        last_ts: float | None = None
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    skipped += 1
                    continue
                if not isinstance(payload, dict):
                    skipped += 1
                    continue
                try:
                    self.insert_event(payload)
                except (ValueError, KeyError, TypeError):
                    skipped += 1
                    continue
                imported += 1
                ts = payload.get("timestamp")
                if isinstance(ts, (int, float)):
                    last_ts = float(ts)
        return ImportReport(imported, skipped, last_ts)

    def import_jsonl_if_empty(self, path: Path) -> ImportReport | None:
        """Importa JSONL só se a tabela estiver vazia (migração one-shot)."""

        if self._imported_once:
            return None
        self._imported_once = True
        if self.count_events() > 0:
            return None
        if not path.is_file():
            return None
        return self.import_jsonl(path)

    def sum_completed_usage(self, *, now: float | None = None) -> UsageTotals:
        """Soma tokens/custo de status=completed no dia e mês UTC."""

        when = time.gmtime(now if now is not None else time.time())
        year, month, day = when.tm_year, when.tm_mon, when.tm_mday
        # Limites aproximados via gmtime no Python após fetch.
        conn = self.open()
        rows = conn.execute(
            """
            SELECT timestamp, input_tokens, output_tokens, estimated_cost_usd
            FROM cloud_usage_events
            WHERE status = 'completed'
            """
        ).fetchall()
        day_tokens = 0
        month_tokens = 0
        day_cost = 0.0
        month_cost = 0.0
        for ts, in_tok, out_tok, cost in rows:
            if not isinstance(ts, (int, float)):
                continue
            stamp = time.gmtime(float(ts))
            if stamp.tm_year != year or stamp.tm_mon != month:
                continue
            tokens = int(in_tok or 0) + int(out_tok or 0)
            cost_f = float(cost) if isinstance(cost, (int, float)) and cost is not None else 0.0
            if cost_f < 0:
                cost_f = 0.0
            month_tokens += tokens
            month_cost += cost_f
            if stamp.tm_mday == day:
                day_tokens += tokens
                day_cost += cost_f
        return UsageTotals(day_tokens, month_tokens, day_cost, month_cost)

    def prune(
        self,
        *,
        retention_days: int | None = None,
        before_ts: float | None = None,
        now: float | None = None,
    ) -> int:
        """Remove completed/failed antigos (S5). Mantém blocked_* / requested.

        Preferir `before_ts`; senão `retention_days` (default 90 via env helper
        do chamador). Retorna quantidade apagada.
        """

        if before_ts is None:
            days = 90 if retention_days is None else max(0, int(retention_days))
            when = now if now is not None else time.time()
            before_ts = float(when) - (days * 86400.0)
        conn = self.open()
        cur = conn.execute(
            """
            DELETE FROM cloud_usage_events
            WHERE timestamp < ?
              AND status IN ('completed', 'failed')
            """,
            (float(before_ts),),
        )
        conn.commit()
        return int(cur.rowcount or 0)


def retention_days_from_env(environ: dict[str, str] | None = None) -> int:
    """YBY_CLOUD_RETENTION_DAYS default 90."""

    source = environ if environ is not None else os.environ
    raw = source.get("YBY_CLOUD_RETENTION_DAYS", "90").strip() or "90"
    try:
        value = int(raw)
    except ValueError:
        return 90
    return max(0, value)


def status_from_result(result: str) -> str:
    """Mapeia result legacy → status; passa status já canônico."""

    raw = (result or "").strip()
    if raw in _RESULT_TO_STATUS:
        return _RESULT_TO_STATUS[raw]
    if raw in _STATUS_TO_RESULT:
        return raw
    # prefixo cloud_ removido
    if raw.startswith("cloud_"):
        candidate = raw[len("cloud_") :]
        if candidate in _STATUS_TO_RESULT:
            return candidate
    raise ValueError(f"status/result desconhecido: {result!r}")


def result_from_status(status: str) -> str:
    if status in _STATUS_TO_RESULT:
        return _STATUS_TO_RESULT[status]
    if status in _RESULT_TO_STATUS:
        return status
    raise ValueError(f"status desconhecido: {status!r}")


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    ts = event.get("timestamp")
    if not isinstance(ts, (int, float)):
        raise ValueError("timestamp obrigatório (número UTC)")
    provider = str(event.get("provider") or "").strip()
    model = str(event.get("model") or "").strip()
    purpose = str(event.get("purpose") or "").strip()
    if not provider or not model or not purpose:
        raise ValueError("provider, model e purpose são obrigatórios")

    if "status" in event and event["status"]:
        status = status_from_result(str(event["status"]))
    elif "result" in event and event["result"]:
        status = status_from_result(str(event["result"]))
    else:
        raise ValueError("status ou result obrigatório")

    in_tok = event.get("input_tokens", event.get("input_tokens_estimate", 0))
    out_tok = event.get("output_tokens", event.get("output_tokens_estimate", 0))
    if not isinstance(in_tok, int) or in_tok < 0:
        in_tok = 0
    if not isinstance(out_tok, int) or out_tok < 0:
        out_tok = 0

    cost = event.get("estimated_cost_usd")
    if cost is not None and not isinstance(cost, (int, float)):
        cost = None
    if isinstance(cost, (int, float)) and cost < 0:
        cost = 0.0

    meta = event.get("meta")
    if meta is None and "meta_json" in event:
        meta_json = event.get("meta_json")
        if meta_json is not None and not isinstance(meta_json, str):
            meta_json = json.dumps(meta_json, ensure_ascii=False)
    elif isinstance(meta, dict):
        bad = FORBIDDEN_KEYS.intersection(meta)
        if bad:
            raise ValueError(f"meta com chaves proibidas: {sorted(bad)}")
        meta_json = json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
    else:
        meta_json = None

    result_legacy = event.get("result")
    if not result_legacy:
        result_legacy = result_from_status(status)
    else:
        result_legacy = str(result_legacy)

    return {
        "timestamp": float(ts),
        "provider": provider,
        "model": model,
        "purpose": purpose,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "estimated_cost_usd": float(cost) if isinstance(cost, (int, float)) else None,
        "status": status,
        "session_id": _opt_str(event.get("session_id")),
        "task_id": _opt_str(event.get("task_id")),
        "prompt_hash": _opt_str(event.get("prompt_hash")),
        "prompt_ref": _opt_str(event.get("prompt_ref")),
        "result_ref": _opt_str(event.get("result_ref")),
        "result": result_legacy,
        "error_code": _opt_str(event.get("error_code")),
        "meta_json": meta_json if isinstance(meta_json, str) else None,
    }


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
