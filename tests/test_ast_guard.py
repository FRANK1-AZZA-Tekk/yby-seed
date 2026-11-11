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


def test_codigo_seguro_simples_passa():
    code = "x = 1 + 2\ny = x * 3\n"
    ok, errors = validate_code_ast(code)
    assert ok is True
    assert errors == []


def test_eval_call_falha():
    ok, errors = validate_code_ast('eval("1+1")\n')
    assert ok is False
    assert any("eval" in e for e in errors)


def test_builtins_subscript_eval_falha():
    code = '__builtins__["eval"]\n'
    ok, errors = validate_code_ast(code)
    assert ok is False
    assert errors


def test_class_dunder_falha():
    ok, errors = validate_code_ast("().__class__\n")
    assert ok is False
    assert any("dunder" in e.lower() for e in errors)


def test_getattr_system_falha():
    ok, errors = validate_code_ast('getattr(obj, "system")\n')
    assert ok is False
    assert any("getattr" in e for e in errors)


def test_import_os_falha():
    ok, errors = validate_code_ast("import os\n")
    assert ok is False


def test_from_os_import_system_falha():
    ok, errors = validate_code_ast("from os import system\n")
    assert ok is False


def test_subprocess_popen_falha():
    code = "import subprocess\nsubprocess.Popen(['ls'])\n"
    ok, errors = validate_code_ast(code)
    assert ok is False


def test_open_call_falha():
    ok, errors = validate_code_ast('open("x")\n')
    assert ok is False
    assert any("open" in e for e in errors)


def test_math_sqrt_passa():
    ok, errors = validate_code_ast("import math\nmath.sqrt(9)\n")
    assert ok is True
    assert errors == []


def test_json_dumps_passa():
    ok, errors = validate_code_ast('import json\njson.dumps({"a": 1})\n')
    assert ok is True
    assert errors == []


def test_builtins_attr_eval_falha():
    code = "f = __builtins__.eval\n"
    ok, errors = validate_code_ast(code)
    assert ok is False
    assert errors


def test_globals_subscript_eval_falha():
    code = 'globals()["eval"]("1+1")\n'
    ok, errors = validate_code_ast(code)
    assert ok is False
    assert errors
