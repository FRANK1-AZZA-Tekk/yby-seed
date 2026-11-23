"""Leitores de uma fonte de verdade por domínio (sem segunda verdade)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from src.assist.reminders import ReminderStore
from src.painel.models import ItemState, PainelItem, PainelResumo
from src.platform.hub import check_ollama

DEVELOP_STATUS_MAP: dict[str, ItemState] = {
    "preparada": "aguardando_aprovacao",
    "enviada": "aguardando_aprovacao",
    "aceita": "executado",
    "rejeitada": "falhou",
}

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


def default_state_dir() -> Path:
    return Path.home() / ".local" / "state" / "yby-seed"


def load_resumo(
    *,
    state_dir: Path | None = None,
    develop_plans_dir: Path | None = None,
    audit_path: Path | None = None,
    reminders_path: Path | None = None,
    incidents_path: Path | None = None,
    ollama_base_url: str = DEFAULT_OLLAMA_URL,
    ollama_timeout: float = 2.0,
    ollama_probe: Callable[[], str] | None = None,
    routine_limit: int = 20,
) -> PainelResumo:
    base = state_dir or default_state_dir()
    audit = audit_path or (base / "assist-audit.jsonl")
    reminders = reminders_path or (base / "assist-reminders.json")
    incidents = incidents_path or (base / "sentinel" / "incidents.json")
    plans = develop_plans_dir
    if plans is None:
        preferred = base / "develop" / "plans"
        legacy = Path(".yby") / "develop" / "plans"
        plans = preferred if preferred.is_dir() else legacy

    if ollama_probe is not None:
        ollama = ollama_probe()
    else:
        ollama = check_ollama(ollama_base_url, timeout=ollama_timeout)

    return PainelResumo(
        ollama=ollama,
        routines=read_routines(audit, limit=routine_limit),
        alerts=read_alerts(incidents),
        reminders=read_reminders(reminders),
        develop_layers=read_develop_layers(plans),
    )


def read_routines(path: Path, *, limit: int = 20) -> list[PainelItem]:
    if not path.is_file():
        return []
    items: list[PainelItem] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in reversed(lines):
        if len(items) >= limit:
            break
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("tool") != "routine.run":
            continue
        meta = event.get("meta") if isinstance(event.get("meta"), dict) else {}
        ok = bool(event.get("ok"))
        ran = meta.get("ran")
        failed = meta.get("failed")
        skipped = meta.get("skipped")
        name = str(meta.get("name") or "rotina")
        state: ItemState = "executado" if ok else "falhou"
        if isinstance(failed, list) and failed:
            state = "falhou"
        detail_parts: list[str] = []
        if isinstance(ran, list) and ran:
            detail_parts.append(f"ran={','.join(str(x) for x in ran)}")
        if isinstance(failed, list) and failed:
            detail_parts.append(f"failed={','.join(str(x) for x in failed)}")
        if isinstance(skipped, list) and skipped:
            detail_parts.append(f"skipped={','.join(str(x) for x in skipped)}")
        if event.get("error"):
            detail_parts.append(str(event["error"]))
        is_partial = bool(
            (isinstance(ran, list) and ran)
            and (
                not ok
                or (isinstance(failed, list) and failed)
                or (isinstance(skipped, list) and skipped)
            )
        )
        items.append(
            PainelItem(
                origin="assist.audit",
                timestamp=float(event.get("timestamp") or 0.0),
                state=state,
                title=name,
                detail="; ".join(detail_parts),
                meta={
                    "partial": is_partial,
                    "ran": ran if isinstance(ran, list) else [],
                    "failed": failed if isinstance(failed, list) else [],
                    "skipped": skipped if isinstance(skipped, list) else [],
                },
            )
        )
    return items


def read_reminders(path: Path) -> list[PainelItem]:
    store = ReminderStore(path)
    try:
        reminders = store.load()
    except OSError:
        return []
    items: list[PainelItem] = []
    for rem in reminders:
        try:
            when = datetime.fromisoformat(rem.when_iso)
            ts = when.timestamp()
        except ValueError:
            ts = time.time()
        state: ItemState = "executado" if rem.delivered else "proposto"
        items.append(
            PainelItem(
                origin="assist.reminders",
                timestamp=ts,
                state=state,
                title=rem.text,
                detail=f"id={rem.id}",
                meta={"id": rem.id, "delivered": rem.delivered},
            )
        )
    return items


def read_alerts(path: Path) -> list[PainelItem]:
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(raw, list):
        rows = raw
    elif isinstance(raw, dict):
        rows = raw.get("incidents", [])
    else:
        rows = []
    items: list[PainelItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        incident_state = str(row.get("state") or "")
        if incident_state != "active":
            continue
        notified = row.get("notified_at")
        try:
            ts = float(notified) if notified is not None else 0.0
        except (TypeError, ValueError):
            ts = 0.0
        items.append(
            PainelItem(
                origin="sentinel.incidents",
                timestamp=ts,
                state="falhou",
                title=str(row.get("rule") or row.get("id") or "alerta"),
                detail=str(row.get("message") or ""),
                meta={
                    "id": row.get("id"),
                    "rule": row.get("rule"),
                    "incident_state": incident_state,
                },
            )
        )
    return items


def read_develop_layers(plans_dir: Path) -> list[PainelItem]:
    if not plans_dir.is_dir():
        return []
    items: list[PainelItem] = []
    for path in sorted(plans_dir.glob("*.json")):
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(plan, dict):
            continue
        layers = plan.get("layers")
        if not isinstance(layers, list):
            continue
        plan_id = str(plan.get("id") or path.stem)
        updated = plan.get("updated_at") or plan.get("timestamp") or 0.0
        try:
            base_ts = float(updated)
        except (TypeError, ValueError):
            base_ts = 0.0
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            status = str(layer.get("status") or "")
            ui_state = DEVELOP_STATUS_MAP.get(status)
            if ui_state is None:
                continue
            layer_id = str(layer.get("id") or "?")
            items.append(
                PainelItem(
                    origin="develop.plans",
                    timestamp=base_ts,
                    state=ui_state,
                    title=f"{plan_id}/{layer_id}",
                    detail=f"status={status}",
                    meta={"plan": plan_id, "layer": layer_id, "status": status},
                )
            )
    return items
