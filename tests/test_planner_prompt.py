"""Projeção de histórico no prompt do planner (caracteres, offline)."""

from __future__ import annotations

import json

import pytest

from src.agent_loop.loop import ControlledAgentLoop
from src.agent_loop.planner import OllamaJsonPlanner
from src.agent_loop.planner_env import DEFAULT_PLANNER_PROMPT_MAX_CHARS
from src.agent_loop.planner_prompt import (
    OMITTED_STEPS_KEY,
    REDUCED_OBSERVATION_MARKER,
    PlannerPromptTooLargeError,
    build_planner_user_prompt,
    planner_prompt_total_chars,
    project_history_json,
)
from src.agent_loop.schemas import parse_planner_step
from src.agent_loop.tools import default_tool_registry


SYSTEM = OllamaJsonPlanner.SYSTEM


def _tools() -> str:
    return default_tool_registry(include_vault=False).describe_for_prompt()


def test_historico_pequeno_preservado() -> None:
    history = [
        {"action": "tool", "name": "echo_json", "arguments": {"message": "olá"}},
        {"action": "tool", "name": "echo_json", "result": {"ok": True}},
    ]
    prompt = build_planner_user_prompt(
        system=SYSTEM,
        task="tarefa curta",
        tools_blurb=_tools(),
        history=history,
        max_total_chars=DEFAULT_PLANNER_PROMPT_MAX_CHARS,
    )
    assert "olá" in prompt
    assert planner_prompt_total_chars(system=SYSTEM, user_prompt=prompt) <= DEFAULT_PLANNER_PROMPT_MAX_CHARS
    assert json.loads(prompt.split("Histórico de passos (JSON):\n", 1)[1].split("\n\n", 1)[0]) == history


def test_historico_grande_cabe_no_teto() -> None:
    big = "x" * 4000
    history = [
        {"action": "tool", "name": "echo_json", "arguments": {"message": f"p{i}"}, "result": {"blob": big}}
        for i in range(12)
    ]
    cap = 2500
    prompt = build_planner_user_prompt(
        system=SYSTEM,
        task="t",
        tools_blurb="- echo_json: teste",
        history=history,
        max_total_chars=cap,
    )
    assert planner_prompt_total_chars(system=SYSTEM, user_prompt=prompt) <= cap
    block = prompt.split("Histórico de passos (JSON):\n", 1)[1].split("\n\nPróximo", 1)[0]
    projected = json.loads(block)
    assert isinstance(projected, list)
    blob = json.dumps(projected, ensure_ascii=False)
    assert (
        any(OMITTED_STEPS_KEY in step for step in projected if isinstance(step, dict))
        or REDUCED_OBSERVATION_MARKER in blob
        or len(projected) < len(history)
    )


def test_observacao_enorme_reduzida_explicitamente() -> None:
    huge = "á" * 5000
    history = [{"action": "tool", "result": {"data": huge}}]
    cap = 800
    prompt = build_planner_user_prompt(
        system=SYSTEM,
        task="café",
        tools_blurb="- echo_json: teste",
        history=history,
        max_total_chars=cap,
    )
    assert planner_prompt_total_chars(system=SYSTEM, user_prompt=prompt) <= cap
    projected = json.loads(prompt.split("Histórico de passos (JSON):\n", 1)[1].split("\n\n", 1)[0])
    blob = json.dumps(projected, ensure_ascii=False)
    assert REDUCED_OBSERVATION_MARKER in blob or OMITTED_STEPS_KEY in blob


def test_historico_projetado_json_valido() -> None:
    history = [{"action": "tool", "result": {"n": i}} for i in range(30)]
    text = project_history_json(history, max_history_json_chars=200)
    json.loads(text)


def test_passos_recentes_em_ordem() -> None:
    history = [{"action": "tool", "name": f"s{i}"} for i in range(8)]
    text = project_history_json(history, max_history_json_chars=180)
    projected = json.loads(text)
    names = [p.get("name") for p in projected if "name" in p]
    assert names == names[-len(names) :]
    assert names[-1] == "s7"
    if any(OMITTED_STEPS_KEY in p for p in projected):
        assert projected[0][OMITTED_STEPS_KEY] >= 1


def test_original_nao_muta() -> None:
    nested = {"msg": "x" * 1500}
    history = [{"action": "tool", "result": nested}]
    before = history[0]["result"]["msg"]  # type: ignore[index]
    build_planner_user_prompt(
        system=SYSTEM,
        task="t",
        tools_blurb="- echo_json: teste",
        history=history,
        max_total_chars=500,
    )
    assert history[0]["result"]["msg"] == before  # type: ignore[index]


def test_unicode_portugues() -> None:
    history = [{"action": "tool", "arguments": {"message": "ação ç ã ö"}}]
    prompt = build_planner_user_prompt(
        system=SYSTEM,
        task="tarefa com acentuação",
        tools_blurb="- echo_json: descrição",
        history=history,
        max_total_chars=1200,
    )
    assert "ação ç" in prompt


def test_limite_exato_e_um_caractere_acima() -> None:
    task = "t"
    tools = "- echo_json: x"
    history: list[dict[str, object]] = []
    prompt = build_planner_user_prompt(
        system=SYSTEM,
        task=task,
        tools_blurb=tools,
        history=history,
        max_total_chars=5000,
    )
    exact = planner_prompt_total_chars(system=SYSTEM, user_prompt=prompt)
    build_planner_user_prompt(
        system=SYSTEM,
        task=task,
        tools_blurb=tools,
        history=history,
        max_total_chars=exact,
    )
    with pytest.raises(PlannerPromptTooLargeError):
        build_planner_user_prompt(
            system=SYSTEM,
            task=task,
            tools_blurb=tools,
            history=history,
            max_total_chars=exact - 1,
        )


def test_obrigatorio_grande_demais_zero_http() -> None:
    with pytest.raises(PlannerPromptTooLargeError, match="conteúdo obrigatório"):
        build_planner_user_prompt(
            system=SYSTEM,
            task="x" * 500,
            tools_blurb="y" * 500,
            history=[],
            max_total_chars=400,
        )


class _CaptureProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.last_prompt = ""
        self.last_system = ""

    def complete(self, prompt: str, *, model: str, system: str, **kwargs: object) -> str:
        self.calls += 1
        self.last_prompt = prompt
        self.last_system = system
        return '{"action":"finish","answer":{}}'


def test_planner_caminho_real_uma_chamada_e_json_format() -> None:
    provider = _CaptureProvider()
    planner = OllamaJsonPlanner(
        provider,  # type: ignore[arg-type]
        model="m",
        planner_json_format=True,
        prompt_max_chars=1500,
    )
    history = [{"action": "tool", "result": {"k": "v"}}]
    planner.plan(task="t", tools_blurb="- echo_json: demo", history=history)
    assert provider.calls == 1
    total = planner_prompt_total_chars(system=provider.last_system, user_prompt=provider.last_prompt)
    assert total <= 1500


def test_loop_contexto_excedido_planner_error_sem_tool() -> None:
    class _ScriptPlanner:
        def plan(self, **_kwargs: object) -> object:
            raise PlannerPromptTooLargeError("conteúdo obrigatório")

    loop = ControlledAgentLoop(
        registry=default_tool_registry(include_vault=False),
        planner=_ScriptPlanner(),  # type: ignore[arg-type]
        max_iterations=3,
    )
    result = loop.run("t")
    assert result.status == "error"
    assert result.steps[-1].kind == "planner_error"
    assert not any(s.kind == "tool" for s in result.steps)


def test_loop_segunda_iteracao_projeta_historico() -> None:
    from pydantic import BaseModel

    from src.agent_loop.tools import ToolRegistry, ToolSpec

    class _VoidArgs(BaseModel):
        pass

    def _fat(_args: BaseModel) -> dict[str, object]:
        return {"ok": True, "blob": "z" * 1200}

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="fat_echo",
            description="retorno grande para teste",
            args_model=_VoidArgs,
            handler=_fat,
        )
    )
    provider = _CaptureProvider()

    class _TwoPhase:
        def __init__(self) -> None:
            self._n = 0
            self._llm = OllamaJsonPlanner(
                provider,  # type: ignore[arg-type]
                model="m",
                prompt_max_chars=650,
            )

        def plan(
            self,
            *,
            task: str,
            tools_blurb: str,
            history: list[dict[str, object]],
        ) -> object:
            if self._n < 2:
                self._n += 1
                return parse_planner_step(
                    '{"action":"tool","name":"fat_echo","arguments":{}}'
                )
            return self._llm.plan(task=task, tools_blurb=tools_blurb, history=history)

    loop = ControlledAgentLoop(registry=registry, planner=_TwoPhase(), max_iterations=5)  # type: ignore[arg-type]
    loop.run("uma execução")
    assert provider.calls == 1
    assert planner_prompt_total_chars(
        system=provider.last_system,
        user_prompt=provider.last_prompt,
    ) <= 650