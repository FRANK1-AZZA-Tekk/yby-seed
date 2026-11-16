"""Testes do registro central de ferramentas."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from src.yby.tools.base import ToolDefinition, ToolRegistry, ToolRisk
from src.yby.tools.registry import create_default_registry
from src.yby.tools.schemas import SearchKnowledgeArgs


class _SlowArgs(BaseModel):
    delay: float = Field(default=0.5, ge=0)


@pytest.fixture
def registry(tmp_path: Path) -> ToolRegistry:
    root = tmp_path / "allowed"
    root.mkdir()
    return create_default_registry(read_roots=[root])


def test_registry_discovers_three_tools(registry: ToolRegistry) -> None:
    assert registry.names() == ["list_files", "read_file", "search_knowledge"]


def test_tool_definitions_expose_input_and_output_schema(registry: ToolRegistry) -> None:
    docs = registry.describe_all()
    search = next(item for item in docs if item["name"] == "search_knowledge")
    assert search["json_schema"]["title"] == "SearchKnowledgeArgs"
    assert search["output_json_schema"]["title"] == "SearchKnowledgeOutput"
    assert search["risk"] == "low"
    assert search["requires_approval"] is False
    assert search["timeout_seconds"] == 60.0


def test_validation_error_structured(registry: ToolRegistry) -> None:
    response = registry.run("search_knowledge", {"query": ""})
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "validation_error"
    assert "errors" in (response.error.details or {})
    assert "traceback" not in response.to_dict()["error"]


def test_unknown_tool_error(registry: ToolRegistry) -> None:
    response = registry.run("nonexistent", {})
    assert response.error is not None
    assert response.error.code == "tool_not_found"


def test_timeout_returns_structured_error() -> None:
    reg = ToolRegistry()

    def slow_handler(args: BaseModel) -> dict:
        assert isinstance(args, _SlowArgs)
        time.sleep(args.delay)
        return {"ok": True}

    reg.register(
        ToolDefinition(
            name="slow_tool",
            description="teste de timeout",
            args_model=_SlowArgs,
            output_model=None,
            risk=ToolRisk.LOW,
            requires_approval=False,
            timeout_seconds=0.05,
            handler=slow_handler,
        )
    )
    response = reg.run("slow_tool", {"delay": 2.0})
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "timeout"


def test_duplicate_register_raises() -> None:
    reg = ToolRegistry()

    def noop(_: BaseModel) -> dict:
        return {}

    spec = ToolDefinition(
        name="dup",
        description="d",
        args_model=SearchKnowledgeArgs,
        output_model=None,
        risk=ToolRisk.LOW,
        requires_approval=False,
        timeout_seconds=1.0,
        handler=noop,
    )
    reg.register(spec)
    with pytest.raises(ValueError, match="já registrada"):
        reg.register(spec)