"""Planners injetáveis: scriptado (testes) e Ollama (opt-in)."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Protocol

from src.agent_loop.schemas import PlannerStep, parse_planner_step
from src.engine.providers import TextProvider


class Planner(Protocol):
    def plan(
        self,
        *,
        task: str,
        tools_blurb: str,
        history: Sequence[dict[str, object]],
    ) -> PlannerStep: ...


class ScriptedPlanner:
    """Sequência fixa de passos JSON (testes e demos sem LLM)."""

    def __init__(self, steps: Sequence[str | dict]) -> None:
        parsed: list[PlannerStep] = []
        for item in steps:
            raw = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
            parsed.append(parse_planner_step(raw))
        self._steps = parsed
        self._index = 0

    def plan(
        self,
        *,
        task: str,
        tools_blurb: str,
        history: Sequence[dict[str, object]],
    ) -> PlannerStep:
        if self._index >= len(self._steps):
            return parse_planner_step('{"action":"abort","reason":"planner script esgotado"}')
        step = self._steps[self._index]
        self._index += 1
        return step


class OllamaJsonPlanner:
    """Uma chamada por iteração; o modelo deve devolver um único JSON."""

    SYSTEM = (
        "Você é o planner do YBY SEED. Responda APENAS com um objeto JSON, sem markdown extra. "
        'Ações: {"action":"tool","name":"...","arguments":{...}} | '
        '{"action":"finish","answer":{...}} | {"action":"abort","reason":"..."}. '
        "Use só tools listadas. Não invente tools."
    )

    def __init__(
        self,
        provider: TextProvider,
        *,
        model: str,
    ) -> None:
        self._provider = provider
        self._model = model

    def plan(
        self,
        *,
        task: str,
        tools_blurb: str,
        history: Sequence[dict[str, object]],
    ) -> PlannerStep:
        history_text = json.dumps(list(history), ensure_ascii=False, indent=0)
        prompt = (
            f"Tarefa: {task}\n\n"
            f"Tools disponíveis:\n{tools_blurb}\n\n"
            f"Histórico de passos (JSON):\n{history_text}\n\n"
            "Próximo passo (um JSON):"
        )
        raw = self._provider.complete(prompt, model=self._model, system=self.SYSTEM)
        return parse_planner_step(raw)


PlannerFactory = Callable[[], Planner]