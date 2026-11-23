"""Roteamento: alias de rotina ou proposta Ollama."""

from __future__ import annotations

import json
import re
from typing import Protocol

from src.assist.capabilities import describe_capabilities_for_prompt
from src.assist.config import AssistConfig, match_routine_alias
from src.assist.types import ToolProposal
from src.engine.providers import ProviderError, TextProvider

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

SYSTEM = (
    "Você é o roteador do YBY assist (PT-BR). "
    "Responda APENAS com um JSON: "
    '{"tool":"<nome>","args":{...}}. '
    "Tools permitidas:\n"
    f"{describe_capabilities_for_prompt()}\n"
    "Não invente tools. Sem shell. Se ambíguo, use tool=clarify."
)


class AssistPlanner(Protocol):
    def propose(self, utterance: str, *, context: str) -> ToolProposal: ...


class ScriptedAssistPlanner:
    """Fila fixa de propostas (testes)."""

    def __init__(self, proposals: list[ToolProposal | dict]) -> None:
        self._items: list[ToolProposal] = []
        for item in proposals:
            if isinstance(item, ToolProposal):
                self._items.append(item)
            else:
                self._items.append(
                    ToolProposal(
                        tool=str(item["tool"]),
                        args=dict(item.get("args") or {}),
                        source="ollama",
                    )
                )
        self._i = 0

    def propose(self, utterance: str, *, context: str) -> ToolProposal:
        if self._i >= len(self._items):
            raise ProviderError("planner script esgotado")
        prop = self._items[self._i]
        self._i += 1
        return prop


class OllamaAssistPlanner:
    def __init__(self, provider: TextProvider, *, model: str) -> None:
        self._provider = provider
        self._model = model

    def propose(self, utterance: str, *, context: str) -> ToolProposal:
        prompt = (
            f"Pedido do usuário: {utterance}\n"
            f"Contexto de sessão: {context}\n"
            "JSON da ação:"
        )
        raw = self._provider.complete(prompt, model=self._model, system=SYSTEM)
        return parse_proposal(raw)


def parse_proposal(raw: str) -> ToolProposal:
    text = raw.strip()
    if not text:
        raise ValueError("proposta vazia do modelo")
    match = _JSON_FENCE.search(text)
    if match:
        text = match.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("nenhum JSON na proposta")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("proposta deve ser objeto")
    tool = payload.get("tool")
    args = payload.get("args") or payload.get("arguments") or {}
    if not isinstance(tool, str) or not tool.strip():
        raise ValueError("campo tool inválido")
    if not isinstance(args, dict):
        raise ValueError("args deve ser objeto")
    return ToolProposal(tool=tool.strip(), args=dict(args), source="ollama")


def resolve_turn_proposal(
    config: AssistConfig,
    utterance: str,
    planner: AssistPlanner | None,
    *,
    context: str = "",
) -> ToolProposal:
    """Alias de rotina tem prioridade e não chama Ollama."""

    rid = match_routine_alias(config, utterance)
    if rid is not None:
        return ToolProposal(
            tool="routine.run",
            args={"name": rid},
            source="alias",
        )
    if planner is None:
        raise ProviderError("Ollama/planner indisponível")
    return planner.propose(utterance, context=context)
