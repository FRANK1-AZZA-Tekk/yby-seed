"""Registro explícito de capacidades do assist."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class AppOpenArgs(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class FilesFindArgs(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=50)


class VaultSearchAssistArgs(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    k: int = Field(default=3, ge=1, le=10)


class SystemStatusArgs(BaseModel):
    pass


class ReminderCreateArgs(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    date: str = Field(min_length=8, max_length=32)  # YYYY-MM-DD
    time: str = Field(min_length=4, max_length=16)  # HH:MM
    tz: str = Field(default="America/Sao_Paulo", min_length=1, max_length=64)


class RoutineRunArgs(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ClarifyArgs(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class ChatArgs(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class SentinelRulesListArgs(BaseModel):
    pass


class SentinelRuleArgs(BaseModel):
    rule: str = Field(min_length=1, max_length=64)


@dataclass(frozen=True)
class Capability:
    name: str
    description: str
    args_model: type[BaseModel]
    requires_confirm: bool
    scope: str
    result_format: str


CAPABILITIES: dict[str, Capability] = {
    "app.open": Capability(
        name="app.open",
        description="Abre um aplicativo cadastrado pelo apelido (sem argv livre).",
        args_model=AppOpenArgs,
        requires_confirm=False,
        scope="apps cadastrados na config",
        result_format="{ok, name, argv}",
    ),
    "files.find": Capability(
        name="files.find",
        description="Busca arquivos por nome só em pastas permitidas.",
        args_model=FilesFindArgs,
        requires_confirm=False,
        scope="search_roots",
        result_format="{ok, hits:[{path, name}], need_choice?}",
    ),
    "vault.search": Capability(
        name="vault.search",
        description="Busca notas no vault (nome+score). Não lê o corpo.",
        args_model=VaultSearchAssistArgs,
        requires_confirm=False,
        scope="YBY_VAULT_PATH",
        result_format="{ok, hits:[{name, score}]}",
    ),
    "system.status": Capability(
        name="system.status",
        description="Espaço em disco e disponibilidade do Ollama (somente leitura).",
        args_model=SystemStatusArgs,
        requires_confirm=False,
        scope="host local",
        result_format="{ok, disk, ollama, errors[]}",
    ),
    "reminder.create": Capability(
        name="reminder.create",
        description="Cria lembrete local após confirmação dos dados exatos.",
        args_model=ReminderCreateArgs,
        requires_confirm=True,
        scope="arquivo local de lembretes",
        result_format="{ok, id, text, when}",
    ),
    "routine.run": Capability(
        name="routine.run",
        description="Executa rotina cadastrada (passos = tools; sem rotina aninhada).",
        args_model=RoutineRunArgs,
        requires_confirm=False,
        scope="routines da config",
        result_format="{ok, ran[], failed?, skipped[]}",
    ),
    "clarify": Capability(
        name="clarify",
        description="Faz uma pergunta de esclarecimento ao usuário.",
        args_model=ClarifyArgs,
        requires_confirm=False,
        scope="sessão",
        result_format="{ok, question}",
    ),
    "chat": Capability(
        name="chat",
        description="Resposta textual sem efeito colateral.",
        args_model=ChatArgs,
        requires_confirm=False,
        scope="sessão",
        result_format="{ok, text}",
    ),
    "sentinel.rules.list": Capability(
        name="sentinel.rules.list",
        description="Lista regras do Sentinela (pausa e incidente ativo).",
        args_model=SentinelRulesListArgs,
        requires_confirm=False,
        scope="sentinel local",
        result_format="{ok, rules[]}",
    ),
    "sentinel.rules.pause": Capability(
        name="sentinel.rules.pause",
        description="Pausa uma regra do Sentinela (não abre/notifica novos).",
        args_model=SentinelRuleArgs,
        requires_confirm=True,
        scope="sentinel local",
        result_format="{ok, rule, paused}",
    ),
    "sentinel.rules.resume": Capability(
        name="sentinel.rules.resume",
        description="Retoma uma regra pausada do Sentinela.",
        args_model=SentinelRuleArgs,
        requires_confirm=True,
        scope="sentinel local",
        result_format="{ok, rule, paused}",
    ),
}


def describe_capabilities_for_prompt() -> str:
    lines = []
    for name in sorted(CAPABILITIES):
        cap = CAPABILITIES[name]
        lines.append(
            f"- {cap.name}: {cap.description} "
            f"(escopo: {cap.scope}; confirm={cap.requires_confirm}; "
            f"resultado: {cap.result_format})"
        )
    return "\n".join(lines)


def validate_tool_args(tool: str, args: dict[str, Any]) -> BaseModel:
    if tool not in CAPABILITIES:
        raise KeyError(f"ferramenta desconhecida: {tool}")
    try:
        return CAPABILITIES[tool].args_model.model_validate(args or {})
    except ValidationError as exc:
        msgs = "; ".join(f"{e['loc']}: {e['msg']}" for e in exc.errors())
        raise ValueError(msgs) from exc
