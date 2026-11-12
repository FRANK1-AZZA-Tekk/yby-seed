"""Scripts de skill devem passar pelo AST guard antes de ativar."""

from src.security.ast_guard import validate_code_ast


def test_skill_script_with_eval_is_blocked() -> None:
    bad = "def x():\n    return eval('1+1')\n"
    ok, issues = validate_code_ast(bad)
    assert not ok
    assert issues
