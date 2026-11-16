"""Testes da ponte roteador ↔ agent_loop e RAG local."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.agent_loop.planner import ScriptedPlanner
from src.agent_loop.tools import default_tool_registry
from src.router.classifier import classify
from src.router.integration import (
    AgentBridge,
    gated_tool_registry,
    retrieve_knowledge,
    temp_vault_with_note,
)
from src.router.policy import ALLOWED_TOOLS


def test_gated_registry_only_allowlisted() -> None:
    gated = gated_tool_registry(default_tool_registry(include_vault=False))
    assert set(gated.names()) <= set(ALLOWED_TOOLS)
    with pytest.raises(KeyError, match="allowlisted"):
        gated.run("shell_run", {})


def test_knowledge_rag_returns_sources(tmp_path: Path) -> None:
    vault = temp_vault_with_note(
        tmp_path / "vault",
        "yby-seed",
        "YBY SEED é um hub local-first com Ollama e vault Obsidian.",
    )
    rag = retrieve_knowledge("o que é YBY SEED", vault=vault, k=2)
    assert rag.hits
    assert rag.sources()
    assert "not_instructions" in rag.as_data_block()
    assert "DADO" in rag.data_only_notice or "dado" in rag.data_only_notice.casefold()


def test_sensitive_action_blocked_without_approval() -> None:
    decision = classify("automatizar backup com script")
    assert decision.requires_approval is True
    bridge = AgentBridge(
        tool_registry=default_tool_registry(include_vault=False),
        planner=ScriptedPlanner([{"action": "finish", "answer": {"ok": True}}]),
    )
    result = bridge.run(user_text="automatizar backup", decision=decision, approved=False)
    assert result.approved is False
    assert result.agent is None
    assert result.blocked_reason is not None


def test_sensitive_action_runs_with_approval() -> None:
    decision = classify("automatizar backup com script")
    bridge = AgentBridge(
        tool_registry=default_tool_registry(include_vault=False),
        planner=ScriptedPlanner(
            [
                {"action": "tool", "name": "echo_json", "arguments": {"message": "dry"}},
                {"action": "finish", "answer": {"done": True}},
            ]
        ),
    )
    result = bridge.run(user_text="automatizar backup", decision=decision, approved=True)
    assert result.approved is True
    assert result.agent is not None
    assert result.agent.status == "completed"
    assert result.tools_used == ["echo_json"]


def test_unknown_tool_not_executed() -> None:
    decision = classify("oi")
    bridge = AgentBridge(
        tool_registry=default_tool_registry(include_vault=False),
        planner=ScriptedPlanner(
            [{"action": "tool", "name": "shell_run", "arguments": {"cmd": "ls"}}]
        ),
    )
    result = bridge.run(user_text="oi", decision=decision, approved=True)
    assert result.agent is not None
    assert result.agent.status == "error"
    assert "shell_run" not in result.tools_used


def test_max_tool_calls_limit_respected() -> None:
    decision = classify("implemente código python")
    # Força limite baixo.
    decision = decision.model_copy(
        update={
            "constraints": decision.constraints.model_copy(
                update={"max_steps": 5, "max_tool_calls": 1}
            )
        }
    )
    bridge = AgentBridge(
        tool_registry=default_tool_registry(include_vault=False),
        planner=ScriptedPlanner(
            [
                {"action": "tool", "name": "echo_json", "arguments": {"message": "1"}},
                {"action": "tool", "name": "echo_json", "arguments": {"message": "2"}},
                {"action": "finish", "answer": {"ok": True}},
            ]
        ),
    )
    result = bridge.run(user_text="código", decision=decision, approved=True)
    assert result.agent is not None
    assert result.agent.status == "error"
    assert result.tools_used == ["echo_json"]
