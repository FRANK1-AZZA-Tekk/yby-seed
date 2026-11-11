"""Testes da guarda AST e sandbox (bypass conhecidos da comunidade)."""

from src.security.ast_guard import validate_code_ast
from src.security.sandbox_executor import SandboxExecutor


def test_rejeita_pathlib_read():
    code = "from pathlib import Path\nPath('/etc/passwd').read_text()\n"
    ok, errors = validate_code_ast(code)
    assert ok is False
    assert errors


def test_rejeita_builtins_open():
    code = "import builtins\nbuiltins.open('/etc/passwd')\n"
    ok, _ = validate_code_ast(code)
    assert ok is False


def test_rejeita_dunder_subclasses():
    code = "().__class__.__bases__[0].__subclasses__()\n"
    ok, errors = validate_code_ast(code)
    assert ok is False
    assert any("dunder" in e.lower() for e in errors)


def test_aceita_math():
    code = "import math\nprint(math.sqrt(4))\n"
    ok, errors = validate_code_ast(code)
    assert ok is True
    assert errors == []


def test_sandbox_rejeita_antes_de_executar():
    sandbox = SandboxExecutor(timeout=2)
    result = sandbox.execute("import os\nos.system('echo pwned')\n")
    assert result["success"] is False
    assert result["error"] == "Código inseguro detectado"


def test_sandbox_retry_nao_muta_timeout():
    sandbox = SandboxExecutor(timeout=2)
    original = sandbox.timeout
    sandbox.execute_with_retry("import time\ntime.sleep(10)\n", max_retries=2)
    assert sandbox.timeout == original
