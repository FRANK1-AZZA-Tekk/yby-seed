"""Log JSONL de aprendizados e relatório por dia UTC (sem auto-merge em docs)."""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from src.engine.secret_gate import find_secret, redact_for_cloud

DEFAULT_LEARN_LOG_PATH = "logs/learn.jsonl"
LEARN_KINDS = frozenset({"success", "failure", "note", "insight"})
LearnKind = Literal["success", "failure", "note", "insight"]

_FORBIDDEN = frozenset({"prompt", "api_key", "response", "text", "audio", "Authorization"})


class LearnError(ValueError):
    """Entrada ou relatório de aprendizado inválidos."""


@dataclass(frozen=True)
class LearnEntry:
    timestamp: float
    day: str
    kind: str
    summary: str
    source: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class DailyReport:
    day: str
    log_path: Path
    total: int
    by_kind: dict[str, int]
    entries: list[LearnEntry]
    note: str = "relatório local; não faz merge automático em docs/LEARNING.md"


def learn_log_path_from_env(environ: dict[str, str] | None = None) -> Path:
    source = environ if environ is not None else os.environ
    raw = source.get("YBY_LEARN_LOG_PATH", DEFAULT_LEARN_LOG_PATH).strip()
    return Path(raw or DEFAULT_LEARN_LOG_PATH)


def append_entry(
    *,
    kind: str,
    summary: str,
    log_path: Path,
    source: str = "cli",
    tags: list[str] | None = None,
    now: float | None = None,
) -> LearnEntry:
    """Acrescenta uma linha JSONL (metadados; sem prompts/chaves)."""

    normalized = kind.strip().casefold()
    if normalized not in LEARN_KINDS:
        allowed = ", ".join(sorted(LEARN_KINDS))
        raise LearnError(f"kind inválido: {kind!r}. Use um de: {allowed}.")

    raw = summary.strip()
    if not raw:
        raise LearnError("summary vazio")
    hit = find_secret(raw)
    if hit is not None:
        raise LearnError(f"summary bloqueado: parece conter segredo ({hit.kind})")
    cleaned = redact_for_cloud(raw)

    ts = now if now is not None else time.time()
    day = time.strftime("%Y-%m-%d", time.gmtime(ts))
    tag_list = tuple(t.strip() for t in (tags or []) if t.strip())
    entry = LearnEntry(
        timestamp=ts,
        day=day,
        kind=normalized,
        summary=cleaned,
        source=source.strip() or "cli",
        tags=tag_list,
    )
    payload: dict[str, Any] = {
        "timestamp": entry.timestamp,
        "day": entry.day,
        "kind": entry.kind,
        "summary": entry.summary,
        "source": entry.source,
        "tags": list(entry.tags),
    }
    for key in _FORBIDDEN:
        if key in payload:
            raise LearnError(f"campo proibido: {key}")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    fd = os.open(log_path, flags, 0o600)
    try:
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        os.close(fd)
        raise
    try:
        log_path.chmod(0o600)
    except OSError:
        pass
    return entry


def read_entries(log_path: Path) -> list[LearnEntry]:
    if not log_path.is_file():
        return []
    out: list[LearnEntry] = []
    with log_path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            entry = _parse_entry(row)
            if entry is not None:
                out.append(entry)
    return out


def report_for_day(
    *,
    log_path: Path,
    day: str | None = None,
    now: float | None = None,
) -> DailyReport:
    """Agrega entradas do dia UTC (padrão: hoje). Não escreve docs."""

    target = day or time.strftime(
        "%Y-%m-%d", time.gmtime(now if now is not None else time.time())
    )
    if len(target) != 10 or target[4] != "-" or target[7] != "-":
        raise LearnError(f"dia inválido: {day!r} (use YYYY-MM-DD)")

    entries = [e for e in read_entries(log_path) if e.day == target]
    by_kind = Counter(e.kind for e in entries)
    return DailyReport(
        day=target,
        log_path=log_path,
        total=len(entries),
        by_kind=dict(sorted(by_kind.items())),
        entries=entries,
    )


def format_report(report: DailyReport) -> str:
    lines = [
        f"dia UTC: {report.day}",
        f"log: {report.log_path}",
        f"total: {report.total}",
        f"nota: {report.note}",
    ]
    if report.by_kind:
        breakdown = ", ".join(f"{k}={v}" for k, v in report.by_kind.items())
        lines.append(f"por kind: {breakdown}")
    else:
        lines.append("por kind: (vazio)")
    for entry in report.entries:
        when = time.strftime("%H:%M:%SZ", time.gmtime(entry.timestamp))
        tags = f" tags={','.join(entry.tags)}" if entry.tags else ""
        lines.append(f"  {when}\t{entry.kind}\t{entry.summary}{tags}")
    return "\n".join(lines)


def _parse_entry(row: dict[str, Any]) -> LearnEntry | None:
    ts = row.get("timestamp")
    kind = row.get("kind")
    summary = row.get("summary")
    if not isinstance(ts, (int, float)) or not isinstance(kind, str):
        return None
    if not isinstance(summary, str) or not summary.strip():
        return None
    day = row.get("day")
    if not isinstance(day, str) or not day:
        day = time.strftime("%Y-%m-%d", time.gmtime(ts))
    source = row.get("source", "unknown")
    if not isinstance(source, str):
        source = "unknown"
    raw_tags = row.get("tags") or []
    tags: list[str] = []
    if isinstance(raw_tags, list):
        tags = [str(t) for t in raw_tags if str(t).strip()]
    return LearnEntry(
        timestamp=float(ts),
        day=day,
        kind=kind.casefold(),
        summary=summary.strip(),
        source=source,
        tags=tuple(tags),
    )
