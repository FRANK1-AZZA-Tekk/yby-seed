"""Coleta local de eventos (offline). Nunca chama APIs de nuvem."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.evo.paths import cloud_usage_log_path
from src.evo.sanitize import sanitize_text, sanitize_value
from src.evo.store import EvoEvent, EvoStore


def _iso_from_unix(ts: float | int | str | None) -> str | None:
    if ts is None:
        return None
    try:
        if isinstance(ts, str):
            if "T" in ts and len(ts) >= 10:
                return ts
            value = float(ts)
        else:
            value = float(ts)
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(microsecond=0).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def event_from_dict(raw: dict[str, Any]) -> EvoEvent:
    """Constrói EvoEvent a partir de dict (sanitize no store)."""

    kind = str(raw.get("kind") or "error").strip()
    summary = str(raw.get("summary") or raw.get("message") or kind)
    source = str(raw.get("source") or "")
    severity = str(raw.get("severity") or "info")
    payload = raw.get("payload")
    if payload is None:
        payload = raw.get("attrs")
    if payload is None:
        payload = {
            k: v
            for k, v in raw.items()
            if k
            not in {
                "kind",
                "summary",
                "message",
                "source",
                "severity",
                "ts",
                "timestamp",
                "ring",
                "schema",
                "attrs",
                "payload",
            }
        }
    if not isinstance(payload, dict):
        payload = {"value": payload}
    ts = raw.get("ts") or _iso_from_unix(raw.get("timestamp"))
    ring = int(raw.get("ring") or 1)
    return EvoEvent(
        kind=kind,
        summary=summary,
        source=source,
        payload=payload if isinstance(payload, dict) else {},
        severity=severity,
        ts=ts if isinstance(ts, str) else None,
        ring=ring,
    )


def ingest_dicts(store: EvoStore, items: Iterable[dict[str, Any]]) -> int:
    """Insere eventos a partir de dicts (simulados ou reais)."""

    return store.add_events(event_from_dict(item) for item in items)


def read_cloud_usage_events(path: Path | None = None) -> list[EvoEvent]:
    """Lê JSONL de uso de nuvem se existir. Só metadados; sem rede."""

    log_path = path or cloud_usage_log_path()
    if not log_path.is_file():
        return []

    events: list[EvoEvent] = []
    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError:
        return []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        # Drop large/sensitive bodies; remaining keys pass through sanitize_value.
        clean = sanitize_value(
            {
                k: v
                for k, v in row.items()
                if k not in {"prompt", "response", "text", "audio"}
            }
        )
        if not isinstance(clean, dict):
            continue
        result = str(clean.get("result") or "unknown")
        provider = str(clean.get("provider") or "?")
        model = str(clean.get("model") or "?")
        purpose = str(clean.get("purpose") or "")
        summary = sanitize_text(f"cloud {result}: {provider}/{model} {purpose}".strip())
        ts = _iso_from_unix(clean.get("timestamp"))
        events.append(
            EvoEvent(
                kind="cloud_call",
                summary=summary,
                source=str(log_path),
                payload=clean,
                severity="warn" if "fail" in result.casefold() else "info",
                ts=ts,
                ring=1,
            )
        )
    return events


def ingest_cloud_log(store: EvoStore, path: Path | None = None) -> int:
    """Importa eventos do JSONL de nuvem (leitura local apenas)."""

    return store.add_events(read_cloud_usage_events(path))


def seed_demo_events(day: str) -> list[dict[str, Any]]:
    """Eventos fake para demos/testes (sem segredos reais)."""

    base = f"{day}T10:00:00+00:00"
    return [
        {
            "schema": "yby.evo.event.v1",
            "kind": "command_run",
            "summary": "yby gate \"ls\" → run",
            "source": "cli",
            "severity": "info",
            "ts": base,
            "ring": 1,
            "payload": {"exit_code": 0, "command": "ls"},
        },
        {
            "kind": "test_result",
            "summary": "pytest tests/test_evo.py — 8 passed",
            "source": "pytest",
            "severity": "info",
            "ts": f"{day}T11:00:00+00:00",
            "payload": {"passed": 8, "failed": 0},
        },
        {
            "kind": "error",
            "summary": "Ollama indisponível em http://127.0.0.1:11434",
            "source": "engine",
            "severity": "error",
            "ts": f"{day}T12:00:00+00:00",
            "payload": {"provider": "ollama"},
        },
        {
            "kind": "task_completed",
            "summary": "docs: atualizar README do evo",
            "source": "agent",
            "severity": "info",
            "ts": f"{day}T13:00:00+00:00",
            "payload": {"files": ["src/evo/README.md"]},
        },
        {
            "kind": "user_feedback",
            "summary": "relatório útil; falta priorizar flaky tests",
            "source": "user",
            "severity": "info",
            "ts": f"{day}T14:00:00+00:00",
            "payload": {"rating": "ok"},
        },
        {
            "kind": "skill_use",
            "summary": "skill walkthrough-artifacts",
            "source": "cursor",
            "severity": "info",
            "ts": f"{day}T15:00:00+00:00",
            "payload": {"skill": "walkthrough-artifacts"},
        },
        {
            "kind": "cloud_call",
            "summary": "cloud cancelled: openrouter/free ask",
            "source": "logs/cloud_usage.jsonl",
            "severity": "warn",
            "ts": f"{day}T16:00:00+00:00",
            "payload": {
                "provider": "openrouter",
                "model": "openrouter/free",
                "result": "cloud_cancelled",
                "purpose": "ask",
                "api_key": "sk-should-never-persist",
            },
        },
    ]
