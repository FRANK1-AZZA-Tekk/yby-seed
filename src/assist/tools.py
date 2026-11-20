"""Handlers das ferramentas cadastradas do assist."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from src.assist.config import AssistConfig
from src.assist.reminders import ReminderStore, build_reminder
from src.assist.types import ToolResult
from src.memory.vault import Vault, VaultError, vault_from_env
from src.platform.hub import check_ollama

Launcher = Callable[[Sequence[str]], None]


def default_launcher(argv: Sequence[str]) -> None:
    subprocess.Popen(list(argv), shell=False, start_new_session=True)


def tool_app_open(
    config: AssistConfig,
    *,
    name: str,
    launcher: Launcher | None = None,
) -> ToolResult:
    key = name.strip().casefold()
    entry = config.apps.get(key)
    if entry is None:
        return ToolResult(
            ok=False,
            tool="app.open",
            error=f"app não cadastrado: {name}",
            narration=f"Não abri nada: '{name}' não está na lista de apps permitidos.",
        )
    run = launcher or default_launcher
    try:
        run(entry.argv)
    except OSError as exc:
        return ToolResult(
            ok=False,
            tool="app.open",
            error=str(exc),
            narration=f"Falha ao abrir '{key}': {exc}",
        )
    return ToolResult(
        ok=True,
        tool="app.open",
        data={"name": key, "argv": list(entry.argv)},
        narration=f"Abri o app cadastrado '{key}'.",
    )


def tool_files_find(
    config: AssistConfig,
    *,
    query: str,
    limit: int,
) -> ToolResult:
    needle = query.strip().casefold()
    if not needle:
        return ToolResult(ok=False, tool="files.find", error="query vazia")
    hits: list[dict[str, str]] = []
    for root in config.search_roots:
        root_res = root.expanduser().resolve()
        if not root_res.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(
            root_res, followlinks=False, topdown=True
        ):
            # Impede descer em symlinks de diretório
            dirnames[:] = [
                d
                for d in dirnames
                if not (Path(dirpath) / d).is_symlink()
            ]
            for fname in filenames:
                path = Path(dirpath) / fname
                if path.is_symlink():
                    # Não segue / não inclui symlink que aponte para fora
                    try:
                        target = path.resolve()
                        target.relative_to(root_res)
                    except (ValueError, OSError):
                        continue
                try:
                    resolved = path.resolve()
                    resolved.relative_to(root_res)
                except (ValueError, OSError):
                    continue
                if needle in fname.casefold():
                    hits.append(
                        {
                            "path": str(resolved),
                            "name": fname,
                        }
                    )
                if len(hits) >= limit:
                    break
            if len(hits) >= limit:
                break
        if len(hits) >= limit:
            break

    if not hits:
        return ToolResult(
            ok=True,
            tool="files.find",
            data={"hits": [], "need_choice": False},
            narration=f"Não encontrei arquivos com '{query}' nas pastas permitidas.",
        )
    need_choice = len(hits) > 1
    narration = (
        f"Encontrei {len(hits)} candidato(s). Digite 'o primeiro', 'o segundo', … "
        "para selecionar (não abro o arquivo sozinho)."
        if need_choice
        else f"Encontrei 1 arquivo: {hits[0]['name']}."
    )
    return ToolResult(
        ok=True,
        tool="files.find",
        data={"hits": hits, "need_choice": need_choice},
        narration=narration,
    )


def tool_vault_search(*, query: str, k: int, vault: Vault | None = None) -> ToolResult:
    try:
        v = vault if vault is not None else vault_from_env()
    except VaultError as exc:
        return ToolResult(
            ok=False,
            tool="vault.search",
            error=str(exc),
            narration=f"Vault indisponível: {exc}",
        )
    hits = v.search(query, k=k)
    payload = [{"name": h.name, "score": round(h.score, 4)} for h in hits]
    if not payload:
        return ToolResult(
            ok=True,
            tool="vault.search",
            data={"hits": []},
            narration="Não encontrei notas correspondentes no índice do vault.",
        )
    return ToolResult(
        ok=True,
        tool="vault.search",
        data={"hits": payload},
        narration=f"Encontrei {len(payload)} nota(s) no índice (nome+score; sem ler o corpo).",
    )


def tool_system_status(config: AssistConfig, *, path: Path | None = None) -> ToolResult:
    errors: list[str] = []
    disk: dict[str, Any] = {}
    try:
        usage = shutil.disk_usage(str(path or Path.home()))
        disk = {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        }
    except OSError as exc:
        errors.append(f"disco: {exc}")

    ollama = check_ollama(config.ollama_base_url, timeout=min(config.ollama_timeout, 5.0))
    if ollama != "ok":
        errors.append(f"ollama: {ollama}")

    parts = []
    if disk:
        free_gb = disk["free_bytes"] / (1024**3)
        parts.append(f"disco livre ≈ {free_gb:.1f} GiB")
    parts.append("Ollama=" + ("ok" if ollama == "ok" else ollama))
    return ToolResult(
        ok=True,
        tool="system.status",
        data={"disk": disk, "ollama": ollama, "errors": errors},
        narration="Status: "
        + "; ".join(parts)
        + ((" | erros: " + "; ".join(errors)) if errors else ""),
    )


def tool_reminder_create_confirmed(
    store: ReminderStore,
    *,
    text: str,
    date: str,
    time: str,
    tz: str,
) -> ToolResult:
    try:
        reminder = build_reminder(text=text, date=date, time=time, tz=tz)
    except ValueError as exc:
        return ToolResult(
            ok=False,
            tool="reminder.create",
            error=str(exc),
            narration=f"Dados de lembrete inválidos: {exc}",
        )
    store.add(reminder)
    return ToolResult(
        ok=True,
        tool="reminder.create",
        data={
            "id": reminder.id,
            "text": reminder.text,
            "when": reminder.when_iso,
            "tz": reminder.tz,
        },
        narration=(
            f"Salvei o lembrete '{reminder.text}' para {date} {time} ({tz}). "
            "A entrega fica a cargo de `yby reminders once` (não desta sessão)."
        ),
    )


def tool_sentinel_rules_list() -> ToolResult:
    from src.sentinel.config import load_sentinel_config
    from src.sentinel.engine import list_rules

    config = load_sentinel_config()
    rows = list_rules(config)
    lines = []
    for row in rows:
        state = "pausada" if row["paused"] else "em observação"
        inc = row["active_incident"]
        if inc:
            lines.append(f"{row['id']}: {state}; incidente ativo ({inc['id']})")
        else:
            lines.append(f"{row['id']}: {state}; sem incidente ativo")
    return ToolResult(
        ok=True,
        tool="sentinel.rules.list",
        data={"rules": rows},
        narration="Regras do Sentinela:\n" + "\n".join(lines),
    )


def tool_sentinel_rules_pause(*, rule: str) -> ToolResult:
    from src.sentinel.config import load_sentinel_config
    from src.sentinel.engine import pause_rule
    from src.sentinel.models import KNOWN_RULES

    rule_id = rule.strip()
    if rule_id not in KNOWN_RULES:
        return ToolResult(
            ok=False,
            tool="sentinel.rules.pause",
            error="regra desconhecida",
            narration=f"Regra desconhecida: {rule_id}. Conhecidas: {', '.join(KNOWN_RULES)}",
        )
    config = load_sentinel_config()
    pause_rule(config, rule_id)
    return ToolResult(
        ok=True,
        tool="sentinel.rules.pause",
        data={"rule": rule_id, "paused": True},
        narration=f"Regra {rule_id} pausada (não abre nem notifica novos alertas).",
    )


def tool_sentinel_rules_resume(*, rule: str) -> ToolResult:
    from src.sentinel.config import load_sentinel_config
    from src.sentinel.engine import resume_rule
    from src.sentinel.models import KNOWN_RULES

    rule_id = rule.strip()
    if rule_id not in KNOWN_RULES:
        return ToolResult(
            ok=False,
            tool="sentinel.rules.resume",
            error="regra desconhecida",
            narration=f"Regra desconhecida: {rule_id}. Conhecidas: {', '.join(KNOWN_RULES)}",
        )
    config = load_sentinel_config()
    resume_rule(config, rule_id)
    return ToolResult(
        ok=True,
        tool="sentinel.rules.resume",
        data={"rule": rule_id, "paused": False},
        narration=f"Regra {rule_id} retomada.",
    )


def tool_clarify(*, question: str) -> ToolResult:
    return ToolResult(
        ok=True,
        tool="clarify",
        data={"question": question},
        narration=question,
    )


def tool_chat(*, text: str) -> ToolResult:
    return ToolResult(
        ok=True,
        tool="chat",
        data={"text": text},
        narration=text,
    )


