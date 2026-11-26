"""Política versionada das tools do agente (offline; sem Ollama, OpenRouter ou rede)."""

from __future__ import annotations

import dataclasses
import os
import subprocess
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from src.agent_loop.loop import ControlledAgentLoop
from src.agent_loop.planner import ScriptedPlanner
from src.agent_loop.tools import (
    ApprovalRequest,
    ToolRegistry,
    ToolSpec,
    default_tool_registry,
)
from src.safety.agent_policy import (
    AgentPolicyError,
    default_agent_policy_path,
    load_agent_policy,
    parse_agent_policy,
)

ROOT = Path(__file__).resolve().parents[1]
HUMAN_ONLY = ("shell.exec", "secrets.read", "deploy", "safety.policy.edit", "data.delete")

VALID = """\
version: 1
default: manual
actions:
  peek:
    autonomy: autonomous
    risk: read
    description: "leitura pura"
  write_note:
    autonomy: manual
    risk: write
    description: "escreve no vault"
  deploy:
    autonomy: human_only
    risk: privileged
    description: "deploy"
"""


class _Args(BaseModel):
    text: str = Field(min_length=1)


def _registry(policy_text: str = VALID, approve=None) -> tuple[ToolRegistry, list[str]]:
    calls: list[str] = []
    registry = ToolRegistry(policy=parse_agent_policy(policy_text), approve=approve)
    for name in ("peek", "write_note", "deploy", "unlisted"):
        registry.register(
            ToolSpec(
                name=name,
                description=name,
                args_model=_Args,
                handler=lambda args, name=name: calls.append(name) or {"ok": True},
            )
        )
    return registry, calls


# a) política válida carrega
def test_repo_policy_loads_and_keeps_default_tools_autonomous():
    policy = load_agent_policy()
    assert policy.version == 1
    assert policy.default == "manual"
    assert policy.decide("echo_json").action == "run"
    assert policy.decide("vault_search").action == "run"
    assert default_agent_policy_path() == ROOT / "config" / "agent-policy.yaml"


def test_default_registry_runs_echo_without_approver():
    registry = default_tool_registry(include_vault=False)
    assert registry.run("echo_json", {"message": "oi"}) == {"ok": True, "message": "oi"}


def test_only_read_tools_are_autonomous_in_repo_policy():
    for action_id, rule in load_agent_policy().actions.items():
        if rule.autonomy == "autonomous":
            assert rule.risk == "read", action_id


# b) política ausente ou inválida falha antes de executar
INVALID = {
    "yaml": "version: 1\ndefault: manual\nactions: [",
    "não mapeamento": "- a\n- b\n",
    "chave extra": VALID + "extra: 1\n",
    "versão": VALID.replace("version: 1", "version: 2"),
    "versão bool": VALID.replace("version: 1", "version: true"),
    "default autonomous": VALID.replace("default: manual", "default: autonomous"),
    "actions vazio": "version: 1\ndefault: manual\nactions: {}\n",
    "id inválido": VALID.replace("  peek:", "  Peek Tool:"),
    "autonomy inválida": VALID.replace("autonomy: autonomous", "autonomy: always"),
    "risk inválido": VALID.replace("risk: read", "risk: none"),
    "campo faltando": VALID.replace('    description: "leitura pura"\n', ""),
    "description vazia": VALID.replace('"leitura pura"', '"  "'),
    "write autonomous": VALID.replace(
        "autonomy: manual\n    risk: write", "autonomy: autonomous\n    risk: write"
    ),
    "external autonomous": VALID.replace(
        "autonomy: manual\n    risk: write", "autonomy: autonomous\n    risk: external"
    ),
    "privileged manual": VALID.replace(
        "autonomy: human_only\n    risk: privileged", "autonomy: manual\n    risk: privileged"
    ),
    "chave duplicada": VALID + "  peek:\n    autonomy: manual\n    risk: read\n"
    '    description: "x"\n',
}


@pytest.mark.parametrize("case", sorted(INVALID))
def test_invalid_policy_rejected(case):
    with pytest.raises(AgentPolicyError):
        parse_agent_policy(INVALID[case])


def test_missing_policy_file_fails(tmp_path):
    with pytest.raises(AgentPolicyError):
        load_agent_policy(tmp_path / "ausente.yaml")


def test_invalid_policy_fails_before_any_tool_runs(tmp_path, monkeypatch):
    bad = tmp_path / "agent-policy.yaml"
    bad.write_text(INVALID["default autonomous"], encoding="utf-8")
    monkeypatch.setattr(
        "src.agent_loop.tools.load_agent_policy", lambda: load_agent_policy(bad)
    )
    with pytest.raises(AgentPolicyError):
        default_tool_registry(include_vault=False)


# c) leitura pura pode ser autonomous
def test_autonomous_read_tool_runs_without_approver():
    registry, calls = _registry()
    assert registry.run("peek", {"text": "x"}) == {"ok": True}
    assert calls == ["peek"]


# d) mutável exige manual
def test_write_tool_requires_approval():
    registry, calls = _registry()
    with pytest.raises(PermissionError, match="aprovação humana"):
        registry.run("write_note", {"text": "x"})
    assert calls == []


# e) segredo/deploy é human_only, mesmo com aprovador que diz sim
@pytest.mark.parametrize("action_id", HUMAN_ONLY)
def test_privileged_actions_refused_in_repo_policy(action_id):
    policy = load_agent_policy()
    assert policy.actions[action_id].autonomy == "human_only"
    assert policy.actions[action_id].risk == "privileged"
    assert policy.decide(action_id).action == "refuse"


def test_human_only_never_asks_approver_nor_executes():
    asked: list[ApprovalRequest] = []
    registry, calls = _registry(approve=lambda req: asked.append(req) or True)
    with pytest.raises(PermissionError, match="recusada"):
        registry.run("deploy", {"text": "prod"})
    assert asked == []
    assert calls == []


# f) ação desconhecida cai no padrão conservador
def test_unlisted_tool_defaults_to_manual():
    registry, calls = _registry()
    assert registry.policy.decide("unlisted").action == "ask"
    with pytest.raises(PermissionError):
        registry.run("unlisted", {"text": "x"})
    assert calls == []


def test_unlisted_tool_with_human_only_default_is_refused():
    policy_text = VALID.replace("default: manual", "default: human_only")
    registry, calls = _registry(policy_text, approve=lambda _req: True)
    with pytest.raises(PermissionError, match="recusada"):
        registry.run("unlisted", {"text": "x"})
    assert calls == []


def test_unregistered_tool_still_blocked():
    registry, _ = _registry(approve=lambda _req: True)
    with pytest.raises(KeyError):
        registry.run("nao_registrada", {})


# g) confirmação negada não executa
@pytest.mark.parametrize("answer", [False, None, "sim", 1])
def test_denied_or_non_bool_approval_does_not_execute(answer):
    registry, calls = _registry(approve=lambda _req: answer)
    with pytest.raises(PermissionError, match="não aprovada"):
        registry.run("write_note", {"text": "x"})
    assert calls == []


def test_approver_sees_validated_arguments_and_decision():
    seen: list[ApprovalRequest] = []
    registry, _ = _registry(approve=lambda req: seen.append(req) or True)
    registry.run("write_note", {"text": "nota"})
    assert seen[0].tool == "write_note"
    assert seen[0].arguments == {"text": "nota"}
    assert seen[0].decision.action == "ask"


def test_invalid_arguments_rejected_before_approval():
    asked: list[ApprovalRequest] = []
    registry, calls = _registry(approve=lambda req: asked.append(req) or True)
    with pytest.raises(ValueError):
        registry.run("write_note", {"text": ""})
    assert asked == [] and calls == []


# h) confirmação aprovada executa uma vez
def test_approved_call_executes_exactly_once():
    registry, calls = _registry(approve=lambda _req: True)
    call = registry.authorize("write_note", {"text": "x"})
    assert calls == []
    assert registry.execute(call) == {"ok": True}
    with pytest.raises(PermissionError, match="já usada"):
        registry.execute(call)
    assert calls == ["write_note"]


def test_authorization_from_other_registry_rejected():
    first, _ = _registry(approve=lambda _req: True)
    second, calls = _registry(approve=lambda _req: True)
    call = first.authorize("write_note", {"text": "x"})
    with pytest.raises(PermissionError):
        second.execute(call)
    assert calls == []


def test_loop_asks_once_and_runs_once_for_manual_tool():
    asked: list[ApprovalRequest] = []
    registry, calls = _registry(approve=lambda req: asked.append(req) or True)
    planner = ScriptedPlanner(
        [
            {"action": "tool", "name": "write_note", "arguments": {"text": "x"}},
            {"action": "finish", "answer": {"ok": True}},
        ]
    )
    result = ControlledAgentLoop(registry=registry, planner=planner).run("t")
    assert result.status == "completed"
    assert len(asked) == 1
    assert calls == ["write_note"]


def test_loop_denied_manual_tool_stops_with_error():
    registry, calls = _registry(approve=lambda _req: False)
    planner = ScriptedPlanner(
        [{"action": "tool", "name": "write_note", "arguments": {"text": "x"}}]
    )
    result = ControlledAgentLoop(registry=registry, planner=planner).run("t")
    assert result.status == "error"
    assert "não aprovada" in (result.steps[-1].error or "")
    assert calls == []


# i) conteúdo de tool / planner não altera a política
def test_policy_is_immutable():
    policy = load_agent_policy()
    with pytest.raises(TypeError):
        policy.actions["deploy"] = policy.actions["echo_json"]  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.default = "autonomous"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.actions["deploy"].autonomy = "autonomous"  # type: ignore[misc]


def test_tool_output_with_policy_payload_does_not_change_decisions():
    hostile = {
        "version": 1,
        "default": "autonomous",
        "actions": {"deploy": {"autonomy": "autonomous", "risk": "read"}},
    }
    registry = ToolRegistry(policy=parse_agent_policy(VALID))
    registry.register(
        ToolSpec(name="peek", description="", args_model=_Args, handler=lambda _a: hostile)
    )
    before = dict(registry.policy.actions)
    planner = ScriptedPlanner(
        [
            {"action": "tool", "name": "peek", "arguments": {"text": "x"}},
            {"action": "tool", "name": "deploy", "arguments": {"text": "agora"}},
        ]
    )
    registry.register(
        ToolSpec(name="deploy", description="", args_model=_Args, handler=lambda _a: {})
    )
    result = ControlledAgentLoop(registry=registry, planner=planner).run("t")
    assert result.status == "error"
    assert "recusada" in (result.steps[-1].error or "")
    assert dict(registry.policy.actions) == before


def test_policy_file_change_after_load_does_not_affect_registry(tmp_path, monkeypatch):
    path = tmp_path / "agent-policy.yaml"
    path.write_text(VALID, encoding="utf-8")
    monkeypatch.setattr("src.agent_loop.tools.load_agent_policy", lambda: load_agent_policy(path))
    registry = ToolRegistry()
    path.write_text(VALID.replace("autonomy: human_only", "autonomy: manual"), encoding="utf-8")
    assert registry.policy.decide("deploy").action == "refuse"


def test_prompt_blurb_does_not_expose_policy():
    blurb = default_tool_registry(include_vault=False).describe_for_prompt()
    assert blurb == "- echo_json: Devolve JSON validado com a mensagem (teste e demos)."


# j) D12, route, cache e orçamento não dependem da política (suítes de engine/route/budget
#    seguem inalteradas); o caminho de shell humano continua na allowlist própria
def test_engine_does_not_reference_agent_policy():
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "src" / "engine").rglob("*.py")
        if any(m in path.read_text(encoding="utf-8") for m in ("agent_policy", "agent-policy"))
    ]
    assert offenders == []


def test_shell_allowlist_path_unchanged():
    from src.actions.runner import run_command

    result = run_command(
        "pwd",
        project_root=ROOT,
        runner=lambda argv, **_kw: subprocess.CompletedProcess(argv, 0, "ok", ""),
        output_fn=lambda _msg: None,
    )
    assert result.decision.action == "run"
    assert result.executed


def _use_policy() -> None:
    registry, calls = _registry(approve=lambda _req: True)
    registry.execute(registry.authorize("peek", {"text": "x"}))
    registry.execute(registry.authorize("write_note", {"text": "x"}))
    load_agent_policy()
    assert calls == ["peek", "write_note"]


_ROUTE_CASES = (
    ("explica uma lista", False, "local", ("local_default",)),
    ("explica uma lista", True, "cloud", ("explicit_heavy",)),
    ("a? b? c?", False, "cloud", ("many_questions",)),
    ("pensa mais sobre isso", False, "cloud", ("heavy_phrase",)),
)


def _routes() -> list[tuple[str, tuple[str, ...]]]:
    from src.engine.routing import decide_route

    decisions = [
        decide_route(
            prompt,
            explicit_heavy=heavy,
            heavy_min_chars=500,
            heavy_min_lines=20,
            heavy_min_questions=3,
            heavy_phrases=("pensa mais",),
        )
        for prompt, heavy, _target, _codes in _ROUTE_CASES
    ]
    return [(d.target, d.codes) for d in decisions]


def test_route_decisions_unchanged_by_policy_use():
    expected = [(target, codes) for _p, _h, target, codes in _ROUTE_CASES]
    assert _routes() == expected
    _use_policy()
    assert _routes() == expected


def test_cache_key_unchanged_by_policy_use():
    from src.engine.cache import ResponseCache

    cache = ResponseCache(ttl_seconds=60)
    key = cache.make_key("ping", model="qwen2.5-coder:3b", system="s")
    _use_policy()
    assert cache.make_key("ping", model="qwen2.5-coder:3b", system="s") == key
    cache.set(key, "pong")
    assert cache.get(key) == "pong"


def test_budget_defaults_unchanged_by_policy_use():
    from src.engine.budget import CloudBudget

    def snapshot() -> tuple[str, bool, bool]:
        budget = CloudBudget.from_env({})
        return budget.cloud_mode, budget.require_confirm, budget.allow_no_tty

    assert snapshot() == ("ask", True, False)
    _use_policy()
    assert snapshot() == ("ask", True, False)


def test_policy_use_does_not_touch_environment(monkeypatch):
    monkeypatch.setenv("YBY_CLOUD_MODE", "ask")
    monkeypatch.setenv("YBY_CLOUD_REQUIRE_CONFIRM", "1")
    before = dict(os.environ)
    _use_policy()
    assert dict(os.environ) == before
