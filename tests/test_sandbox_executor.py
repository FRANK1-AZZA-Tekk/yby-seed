"""Sandbox: restrições em runtime além da guarda AST."""

from __future__ import annotations

import pytest

from src.security.sandbox_executor import SandboxExecutor


@pytest.fixture
def sandbox() -> SandboxExecutor:
    return SandboxExecutor(timeout=3, memory_limit_mb=128)


def test_runtime_eval_falha(sandbox: SandboxExecutor) -> None:
    result = sandbox.execute('eval("1+1")\n')
    assert result["success"] is False


def test_runtime_builtins_subscript_eval_falha(sandbox: SandboxExecutor) -> None:
    result = sandbox.execute('__builtins__["eval"]("1+1")\n')
    assert result["success"] is False


def test_runtime_class_dunder_falha(sandbox: SandboxExecutor) -> None:
    result = sandbox.execute("().__class__\n")
    assert result["success"] is False


def test_runtime_getattr_system_falha(sandbox: SandboxExecutor) -> None:
    result = sandbox.execute('getattr(obj, "system")\n')
    assert result["success"] is False


def test_runtime_codigo_seguro_math_json(sandbox: SandboxExecutor) -> None:
    code = 'import math\nimport json\nprint(math.sqrt(4))\nprint(json.dumps({"ok": 1}))\n'
    result = sandbox.execute(code)
    assert result["success"] is True, result
    assert "2.0" in result["stdout"]
    assert '"ok"' in result["stdout"]


def test_runtime_ofuscacao_chr_getattr_falha(sandbox: SandboxExecutor) -> None:
    code = 'name = chr(101)+chr(118)+chr(97)+chr(108)\ngetattr(__builtins__, name)("1+1")\n'
    result = sandbox.execute(code)
    assert result["success"] is False


def test_execute_with_retry_preserva_timeout(sandbox: SandboxExecutor) -> None:
    original = sandbox.timeout
    sandbox.execute_with_retry("import math\nprint(1)\n", max_retries=2)
    assert sandbox.timeout == original
