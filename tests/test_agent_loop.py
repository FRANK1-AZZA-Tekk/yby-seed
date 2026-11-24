"""Testes do loop de agente P0 (sem Ollama)."""

from __future__ import annotations

import json
import time

import pytest
from pydantic import BaseModel, Field

from src.agent_loop.loop import ControlledAgentLoop
from src.agent_loop.planner import OllamaJsonPlanner, ScriptedPlanner
from src.agent_loop.planner_env import planner_ollama_format_from_env
from src.agent_loop.schemas import parse_planner_step
from src.agent_loop.tools import ToolRegistry, ToolSpec, default_tool_registry
from src.engine.config import EngineConfigError
from src.engine.providers import OllamaProvider, ProviderError


def test_parse_planner_step_json_invalido_levanta_json_decode_error() -> None:
    with pytest.raises(json.JSONDecodeError):
        parse_planner_step('{"action": }')


def test_parse_planner_step_acao_desconhecida_levanta_value_error() -> None:
    with pytest.raises(ValueError, match="ação desconhecida"):
        parse_planner_step('{"action":"noop","name":"x"}')


class _FakeTextProvider:
    """Devolve texto fixo em `complete` — limite de I/O para OllamaJsonPlanner."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        self.calls += 1
        return self.response


def _loop_com_ollama_planner(response: str) -> tuple[ControlledAgentLoop, _FakeTextProvider]:
    provider = _FakeTextProvider(response)
    planner = OllamaJsonPlanner(provider, model="qwen2.5-coder:3b")
    loop = ControlledAgentLoop(
        registry=default_tool_registry(include_vault=False),
        planner=planner,
        max_iterations=5,
    )
    return loop, provider


def test_planner_fake_legado_com_json_format_ligado() -> None:
    provider = _FakeTextProvider('{"action":"finish","answer":{"ok":true}}')
    planner = OllamaJsonPlanner(
        provider,
        model="qwen2.5-coder:3b",
        planner_json_format=True,
    )
    step = planner.plan(task="t", tools_blurb="tools", history=[])
    assert step.action == "finish"
    assert provider.calls == 1


def test_planner_env_invalido_falha_antes_de_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(EngineConfigError, match="YBY_PLANNER_OLLAMA_FORMAT"):
        planner_ollama_format_from_env({"YBY_PLANNER_OLLAMA_FORMAT": "schema"})
    monkeypatch.setenv("YBY_PLANNER_OLLAMA_FORMAT", "schema")
    with pytest.raises(EngineConfigError, match="YBY_PLANNER_OLLAMA_FORMAT"):
        OllamaJsonPlanner(
            _FakeTextProvider("{}"),
            model="qwen2.5-coder:3b",
        )


class _Resp:
    def __init__(self, status: int, payload: object | None = None) -> None:
        self.status_code = status
        self._payload = payload or {"response": "ok"}

    def json(self) -> object:
        return self._payload


class _PlannerSession:
    def __init__(self, response: _Resp) -> None:
        self.response = response
        self.posts: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> _Resp:
        self.posts.append({"url": url, **kwargs})
        return self.response


def test_planner_opt_in_alcanca_post_com_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YBY_PLANNER_OLLAMA_FORMAT", "json")
    session = _PlannerSession(
        _Resp(200, {"response": '{"action":"finish","answer":{"n":1}}'})
    )
    provider = OllamaProvider("http://127.0.0.1:11434", timeout=1, session=session)
    planner = OllamaJsonPlanner(provider, model="qwen2.5-coder:3b")
    step = planner.plan(task="t", tools_blurb="t", history=[])
    assert step.action == "finish"
    assert len(session.posts) == 1
    body = session.posts[0]["json"]
    assert isinstance(body, dict)
    assert body.get("format") == "json"


def test_planner_http_erro_uma_chamada_sem_tool() -> None:
    session = _PlannerSession(_Resp(400, {"error": "bad request"}))
    provider = OllamaProvider("http://127.0.0.1:11434", timeout=1, session=session)
    planner = OllamaJsonPlanner(
        provider,
        model="qwen2.5-coder:3b",
        planner_json_format=True,
    )
    loop = ControlledAgentLoop(
        registry=default_tool_registry(include_vault=False),
        planner=planner,
        max_iterations=3,
    )
    result = loop.run("tarefa")
    assert result.status == "error"
    assert result.steps[-1].kind == "planner_error"
    assert len(session.posts) == 1
    assert session.posts[0]["json"]["format"] == "json"
    assert not any(step.kind == "tool" for step in result.steps)


def test_planner_json_invalido_vira_planner_error_sem_tool() -> None:
    loop, provider = _loop_com_ollama_planner('{"action": }')
    result = loop.run("tarefa")
    assert result.status == "error"
    assert result.steps[-1].kind == "planner_error"
    assert result.steps[-1].error is not None
    assert provider.calls == 1
    assert not any(step.kind == "tool" for step in result.steps)


def test_planner_acao_desconhecida_vira_planner_error_sem_tool() -> None:
    loop, provider = _loop_com_ollama_planner('{"action":"fly_away","name":"x"}')
    result = loop.run("tarefa")
    assert result.status == "error"
    assert result.steps[-1].kind == "planner_error"
    assert "ação desconhecida" in (result.steps[-1].error or "")
    assert provider.calls == 1
    assert not any(step.kind == "tool" for step in result.steps)


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


def test_provider_error_vira_status_error() -> None:
    class _Down:
        def plan(self, **_kwargs: object) -> object:
            raise ProviderError("Ollama indisponível.")

    loop = ControlledAgentLoop(
        registry=default_tool_registry(include_vault=False),
        planner=_Down(),  # type: ignore[arg-type]
        max_iterations=2,
    )
    result = loop.run("oi")
    assert result.status == "error"
    assert "indisponível" in (result.steps[-1].error or "")


class _SlowArgs(BaseModel):
    seconds: float = Field(ge=0.01, le=10.0)


def _slow_handler(args: BaseModel) -> dict[str, object]:
    assert isinstance(args, _SlowArgs)
    time.sleep(args.seconds)
    return {"ok": True}


def test_tool_timeout_interrupts_hung_tool() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="slow_echo",
            description="demora de propósito",
            args_model=_SlowArgs,
            handler=_slow_handler,
        )
    )
    script = [{"action": "tool", "name": "slow_echo", "arguments": {"seconds": 0.25}}]
    loop = ControlledAgentLoop(
        registry=registry,
        planner=ScriptedPlanner(script),
        max_iterations=2,
        tool_timeout_seconds=0.05,
    )
    result = loop.run("timeout")
    assert result.status == "error"
    assert result.steps[-1].error is not None
    assert "excedeu" in (result.steps[-1].error or "")


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