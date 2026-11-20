"""Política do assist: escopo cadastrado + confirmação."""

from __future__ import annotations

from src.assist.capabilities import CAPABILITIES
from src.assist.config import AssistConfig
from src.assist.types import PolicyDecision, ToolProposal


def decide_policy(config: AssistConfig, proposal: ToolProposal) -> PolicyDecision:
    tool = proposal.tool
    if tool not in CAPABILITIES:
        return PolicyDecision("refuse", f"ferramenta desconhecida: {tool}")

    cap = CAPABILITIES[tool]
    args = proposal.args

    if tool == "app.open":
        name = str(args.get("name", "")).casefold()
        if name not in config.apps:
            return PolicyDecision("refuse", f"app não cadastrado: {name}")
        return PolicyDecision("allow", "app cadastrado")

    if tool == "files.find":
        if not config.search_roots:
            return PolicyDecision("refuse", "nenhuma search_root configurada")
        return PolicyDecision("allow", "busca em pastas permitidas")

    if tool == "vault.search":
        return PolicyDecision("allow", "busca somente leitura no vault")

    if tool == "system.status":
        return PolicyDecision("allow", "status somente leitura")

    if tool == "reminder.create":
        return PolicyDecision("confirm", "lembrete exige confirmação dos dados exatos")

    if tool == "routine.run":
        name = str(args.get("name", "")).casefold()
        if name not in config.routines:
            return PolicyDecision("refuse", f"rotina não cadastrada: {name}")
        return PolicyDecision("allow", "rotina cadastrada")

    if tool in {"clarify", "chat"}:
        return PolicyDecision("allow", "sem efeito colateral")

    if tool == "sentinel.rules.list":
        return PolicyDecision("allow", "listagem somente leitura")

    if tool in {"sentinel.rules.pause", "sentinel.rules.resume"}:
        return PolicyDecision("confirm", "altera observação do Sentinela")

    if cap.requires_confirm:
        return PolicyDecision("confirm", "confirmação exigida pela capacidade")
    return PolicyDecision("allow", "capacidade registrada")
