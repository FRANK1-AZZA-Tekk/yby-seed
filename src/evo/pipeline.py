"""Orquestra ingestão → agregação → análise local → relatório.

Estados mínimos v0.1: observing → analyzing → completed (sem apply).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.evo.aggregate import DayAggregate, aggregate_day
from src.evo.analyze import AnalysisResult, TextCompleter, analyze_day
from src.evo.collect import ingest_cloud_log, ingest_dicts, seed_demo_events
from src.evo.paths import resolve_db_path, resolve_reports_dir
from src.evo.report import render_markdown, write_report
from src.evo.store import EvoStore

DEFAULT_LOCAL_MODEL = "qwen2.5-coder:3b"
_USE_DEFAULT_COMPLETER = object()


@dataclass
class ReportBundle:
    day: str
    aggregate: DayAggregate
    analysis: AnalysisResult
    markdown: str
    path: Path
    db_path: Path
    cycle_state: str = "completed"


def open_store(db_path: Path | str | None = None) -> EvoStore:
    return EvoStore(resolve_db_path(db_path))


def build_local_completer() -> TextCompleter | None:
    """Ollama local apenas. Sem credenciais de nuvem. None se desligado."""

    if os.environ.get("YBY_EVO_NO_OLLAMA", "").strip().casefold() in {"1", "true", "yes"}:
        return None
    try:
        from src.engine.config import EngineConfig
        from src.engine.providers import OllamaProvider
    except ImportError:
        return None
    cfg = EngineConfig.from_env()
    return OllamaProvider(cfg.ollama_base_url, timeout=min(cfg.ollama_timeout, 60.0))


def local_model_name() -> str:
    raw = os.environ.get("YBY_EVO_MODEL", "").strip()
    if raw:
        return raw
    raw = os.environ.get("YBY_LOCAL_MODEL", "").strip()
    return raw or DEFAULT_LOCAL_MODEL


def generate_report(
    day: str,
    *,
    db_path: Path | str | None = None,
    reports_dir: Path | str | None = None,
    completer: Any = _USE_DEFAULT_COMPLETER,
    model: str | None = None,
    seed_demo: bool = False,
    ingest_cloud: bool = True,
    extra_events: list[dict[str, Any]] | None = None,
) -> ReportBundle:
    """Gera relatório para `day`. Completer default = Ollama local se disponível."""

    store_path = resolve_db_path(db_path)
    out_dir = resolve_reports_dir(reports_dir)
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    cycle_id = f"cycle_{day}"

    with open_store(store_path) as store:
        store.upsert_cycle(cycle_id, day=day, state="observing", started_at=started)
        if seed_demo:
            ingest_dicts(store, seed_demo_events(day))
        if extra_events:
            ingest_dicts(store, extra_events)
        if ingest_cloud:
            ingest_cloud_log(store)

        events = store.events_for_day(day)
        store.upsert_cycle(cycle_id, day=day, state="analyzing", started_at=started)

    agg = aggregate_day(day, events)

    if completer is _USE_DEFAULT_COMPLETER:
        resolved: TextCompleter | None = build_local_completer()
    else:
        resolved = completer

    analysis = analyze_day(agg, completer=resolved, model=model or local_model_name())
    md = render_markdown(agg, analysis)
    path = write_report(md, day, reports_dir=out_dir)
    finished = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    with open_store(store_path) as store:
        store.upsert_cycle(
            cycle_id,
            day=day,
            state="completed",
            started_at=started,
            finished_at=finished,
            report_path=str(path),
        )

    return ReportBundle(
        day=day,
        aggregate=agg,
        analysis=analysis,
        markdown=md,
        path=path,
        db_path=store_path,
        cycle_state="completed",
    )
