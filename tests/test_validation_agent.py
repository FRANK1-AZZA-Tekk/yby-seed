"""Testes unitários funcionais para o ValidationAgent."""

import pytest

from src.agents.validation_agent import ValidationAgent


@pytest.fixture
def validator():
    """ValidationAgent sem dependências externas."""
    return ValidationAgent()


CODIGO_VALIDO = '''
import os

def main():
    print("Olá, YBY!")

if __name__ == "__main__":
    main()
'''

CODIGO_SINTAXE_INVALIDA = '''
def main()
    print("erro")
'''

CODIGO_PERIGOSO = '''
import os

def main():
    os.system("rm -rf /")

if __name__ == "__main__":
    main()
'''

CODIGO_SEM_ESTRUTURA = '''
import os

def main():
    print("sem if __name__")
'''


def test_codigo_valido(validator):
    """Código limpo deve passar em todas as validações."""
    is_valid, errors = validator.validate(CODIGO_VALIDO)

    assert is_valid is True
    assert errors == []


def test_sintaxe_invalida(validator):
    """Código com erro de sintaxe deve falhar."""
    is_valid, errors = validator.validate(CODIGO_SINTAXE_INVALIDA)

    assert is_valid is False
    assert any("Erro de sintaxe" in e for e in errors)


def test_codigo_perigoso(validator):
    """Código com os.system/rm -rf deve ser rejeitado."""
    is_valid, errors = validator.validate(CODIGO_PERIGOSO)

    assert is_valid is False
    assert any("os.system" in e for e in errors)
    assert any("rm -rf" in e for e in errors)


def test_estrutura_incompleta(validator):
    """Código sem if __name__ deve falhar na estrutura."""
    is_valid, errors = validator.validate(CODIGO_SEM_ESTRUTURA)

    assert is_valid is False
    assert any("Seção ausente" in e for e in errors)


def test_sugestoes_para_codigo_valido(validator):
    """Código válido não deve gerar sugestões."""
    sugestao = validator.suggest_fixes(CODIGO_VALIDO, [])

    assert "sem correções necessárias" in sugestao


def test_sugestoes_para_eval(validator):
    """Erro de eval deve sugerir ast.literal_eval."""
    sugestao = validator.suggest_fixes(
        CODIGO_PERIGOSO,
        ["⚠️  Padrão perigoso detectado: eval("]
    )

    assert "ast.literal_eval" in sugestao
