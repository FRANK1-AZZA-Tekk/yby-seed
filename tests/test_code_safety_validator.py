"""Testes para validação de segurança no código gerado."""

import pytest

from src.security.code_safety_validator import (
    CodeSafetyValidator,
    SafetyResult,
)


@pytest.fixture
def validator():
    """CodeSafetyValidator pronto para uso."""
    return CodeSafetyValidator()


def test_codigo_seguro(validator):
    """Código seguro deve passar na validação."""
    code = """
import os

def main():
    print("hello")

if __name__ == "__main__":
    main()
"""

    result = validator.validate(code)

    assert result.is_safe is True
    assert result.syntax_valid is True
    assert result.issues == []
    assert result.dangerous_imports == []
    assert result.dangerous_calls == []


def test_codigo_com_erro_sintaxe(validator):
    """Código com erro de sintaxe deve falhar."""
    code = "def main(:\n    pass"

    result = validator.validate(code)

    assert result.is_safe is False
    assert result.syntax_valid is False
    assert len(result.issues) > 0


def test_codigo_com_import_perigoso(validator):
    """Import perigoso deve ser detectado."""
    code = """
import subprocess

def main():
    subprocess.run(["ls"])
"""

    result = validator.validate(code)

    assert result.is_safe is False
    assert "subprocess" in result.dangerous_imports
    assert len(result.issues) > 0


def test_codigo_com_chamada_perigosa(validator):
    """Chamada perigosa deve ser detectada."""
    code = """
def main():
    eval("print('hello')")
"""

    result = validator.validate(code)

    assert result.is_safe is False
    assert "eval" in result.dangerous_calls
    assert len(result.issues) > 0


def test_codigo_com_multiplas_problemas(validator):
    """Código com múltiplos problemas deve detectar todos."""
    code = """
import subprocess

def main():
    eval("print('hello')")
    exec("x = 1")
"""

    result = validator.validate(code)

    assert result.is_safe is False
    assert "subprocess" in result.dangerous_imports
    assert "eval" in result.dangerous_calls
    assert "exec" in result.dangerous_calls
    assert len(result.issues) >= 3


def test_safety_result_schema():
    """SafetyResult deve aceitar dados válidos."""
    result = SafetyResult(
        is_safe=True,
        issues=[],
        syntax_valid=True,
        dangerous_imports=[],
        dangerous_calls=[],
    )

    assert result.is_safe is True
    assert result.syntax_valid is True
    assert result.issues == []
