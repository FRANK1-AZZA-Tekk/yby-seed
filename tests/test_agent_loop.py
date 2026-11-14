"""Testes do loop de agente P0 (sem Ollama)."""

from __future__ import annotations

import json

import pytest

from src.agent_loop.loop import ControlledAgentLoop
from src.agent_loop.planner import ScriptedPlanner
from src.agent_loop.schemas import parse_planner_step
from src.agent_loop.tools import default_tool_registry


def test_parse_planner_step_tool() -> None:
    step = parse_planner_step(
        '{"action":"tool","name":"echo_json","arguments":{"message":"oi"}}'
    )
    assert step.action == "tool"
    assert step.name == "echo_json"


def test_parse_planner_step_accepts_tool_then_registry_validates() -> None:
    step = parse_planner_step(
        '{"action":"tool","name":"echo_json","arguments":{"message":""}}'
    )
    assert step.name == "echo_json"
    registry = default_tool_registry(include_vault=False)
    with pytest.raises(ValueError, match="message"):
        registry.run(step.name, step.arguments)


def test_echo_tool_validation_fails_on_empty_message() -> None:
    registry = default_tool_registry(include_vault=False)
    with pytest.raises(ValueError, match="message"):
        registry.run("echo_json", {"message": ""})


def test_unknown_tool_blocked() -> None:
    registry = default_tool_registry(include_vault=False)
    with pytest.raises(KeyError, match="allowlisted"):
        registry.run("shell_run", {"cmd": "ls"})


def test_scripted_planner_completes_with_structured_answer() -> None:
    script = [
        {"action": "tool", "name": "echo_json", "arguments": {"message": "passo1"}},
        {
            "action": "finish",
            "answer": {"summary": "ok", "validated": True},
        },
    ]
    loop = ControlledAgentLoop(
        registry=default_tool_registry(include_vault=False),
        planner=ScriptedPlanner(script),
        max_iterations=5,
    )
    result = loop.run("tarefa de teste")
    assert result.status == "completed"
    assert result.final_answer == {"summary": "ok", "validated": True}
    assert result.iterations == 2
    assert result.steps[0].kind == "tool"


def test_max_iterations_enforced() -> None:
    script = [
        {"action": "tool", "name": "echo_json", "arguments": {"message": f"n{i}"}}
        for i in range(20)
    ]
    loop = ControlledAgentLoop(
        registry=default_tool_registry(include_vault=False),
        planner=ScriptedPlanner(script),
        max_iterations=3,
    )
    result = loop.run("loop longo")
    assert result.status == "max_steps"
    assert result.iterations == 3


def test_abort_stops_loop() -> None:
    script = [
        {"action": "abort", "reason": "usuário cancelou"},
    ]
    loop = ControlledAgentLoop(
        registry=default_tool_registry(include_vault=False),
        planner=ScriptedPlanner(script),
        max_iterations=8,
    )
    result = loop.run("cancelar")
    assert result.status == "aborted"
    assert result.abort_reason == "usuário cancelou"


def test_tool_error_stops_without_shell() -> None:
    script = [
        {"action": "tool", "name": "echo_json", "arguments": {"message": "x"}},
        {"action": "tool", "name": "nao_existe", "arguments": {}},
    ]
    loop = ControlledAgentLoop(
        registry=default_tool_registry(include_vault=False),
        planner=ScriptedPlanner(script),
        max_iterations=5,
    )
    result = loop.run("falha tool")
    assert result.status == "error"
    assert result.steps[-1].error is not None


def test_result_serializable_json() -> None:
    loop = ControlledAgentLoop(
        registry=default_tool_registry(include_vault=False),
        planner=ScriptedPlanner(
            [
                {
                    "action": "finish",
                    "answer": {"n": 1},
                }
            ]
        ),
        max_iterations=2,
    )
    result = loop.run("json")
    payload = {
        "status": result.status,
        "final_answer": result.final_answer,
        "steps": len(result.steps),
    }
    json.dumps(payload)