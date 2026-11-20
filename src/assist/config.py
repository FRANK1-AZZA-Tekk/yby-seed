"""Configuração local do assist (JSON)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppEntry:
    argv: tuple[str, ...]


@dataclass(frozen=True)
class RoutineStep:
    tool: str
    args: dict[str, Any]


@dataclass(frozen=True)
class RoutineEntry:
    aliases: tuple[str, ...]
    steps: tuple[RoutineStep, ...]


@dataclass(frozen=True)
class AssistConfig:
    apps: dict[str, AppEntry]
    search_roots: tuple[Path, ...]
    routines: dict[str, RoutineEntry]
    reminders_path: Path
    audit_log_path: Path
    ollama_base_url: str
    ollama_timeout: float
    find_limit_default: int = 10

    def app_names(self) -> list[str]:
        return sorted(self.apps)

    def routine_ids(self) -> list[str]:
        return sorted(self.routines)


def default_state_dir() -> Path:
    return Path.home() / ".local" / "state" / "yby-seed"


def load_assist_config(
    path: Path | None = None,
    *,
    environ: dict[str, str] | None = None,
) -> AssistConfig:
    source = environ if environ is not None else os.environ
    raw_path = path
    if raw_path is None:
        env = source.get("YBY_ASSIST_CONFIG", "").strip()
        raw_path = Path(env) if env else None
    if raw_path is None or not raw_path.is_file():
        return _empty_config(source)

    data = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config assist deve ser um objeto JSON")

    apps: dict[str, AppEntry] = {}
    for name, spec in (data.get("apps") or {}).items():
        if not isinstance(spec, dict):
            continue
        argv = spec.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
            continue
        apps[str(name).casefold()] = AppEntry(argv=tuple(argv))

    roots: list[Path] = []
    for item in data.get("search_roots") or []:
        if isinstance(item, str) and item.strip():
            roots.append(Path(item).expanduser())

    routines: dict[str, RoutineEntry] = {}
    for rid, spec in (data.get("routines") or {}).items():
        if not isinstance(spec, dict):
            continue
        aliases_raw = spec.get("aliases") or []
        steps_raw = spec.get("steps") or []
        if not isinstance(aliases_raw, list) or not isinstance(steps_raw, list):
            continue
        aliases = tuple(
            _norm_alias(a) for a in aliases_raw if isinstance(a, str) and a.strip()
        )
        steps: list[RoutineStep] = []
        for step in steps_raw:
            if not isinstance(step, dict):
                continue
            tool = step.get("tool")
            args = step.get("args") or {}
            if not isinstance(tool, str) or not isinstance(args, dict):
                continue
            if tool == "routine.run":
                raise ValueError("rotinas não podem chamar routine.run neste PR")
            steps.append(RoutineStep(tool=tool, args=dict(args)))
        if not steps:
            continue
        key = str(rid).casefold()
        # id também conta como alias
        alias_set = tuple(dict.fromkeys((key, *aliases)))
        routines[key] = RoutineEntry(aliases=alias_set, steps=tuple(steps))

    state = default_state_dir()
    reminders = Path(
        str(data.get("reminders_path") or state / "assist-reminders.json")
    ).expanduser()
    audit = Path(
        str(data.get("audit_log_path") or state / "assist-audit.jsonl")
    ).expanduser()

    from src.engine.config import EngineConfig

    cfg = EngineConfig.from_env(source)
    return AssistConfig(
        apps=apps,
        search_roots=tuple(roots),
        routines=routines,
        reminders_path=reminders,
        audit_log_path=audit,
        ollama_base_url=cfg.ollama_base_url,
        ollama_timeout=cfg.ollama_timeout,
        find_limit_default=int(data.get("find_limit_default") or 10),
    )


def _empty_config(source: dict[str, str]) -> AssistConfig:
    from src.engine.config import EngineConfig

    cfg = EngineConfig.from_env(source)
    state = default_state_dir()
    return AssistConfig(
        apps={},
        search_roots=(),
        routines={},
        reminders_path=state / "assist-reminders.json",
        audit_log_path=state / "assist-audit.jsonl",
        ollama_base_url=cfg.ollama_base_url,
        ollama_timeout=cfg.ollama_timeout,
    )


def _norm_alias(text: str) -> str:
    return " ".join(text.casefold().split())


def match_routine_alias(config: AssistConfig, utterance: str) -> str | None:
    """Match exato de alias (casefold + espaços). Não faz fuzzy."""

    needle = _norm_alias(utterance)
    if not needle:
        return None
    for rid, entry in config.routines.items():
        if needle == rid or needle in entry.aliases:
            return rid
    return None
