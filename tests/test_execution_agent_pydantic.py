"""Testes para validação Pydantic no ExecutionAgent."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from src.agents.execution_agent import ExecutionAgent, GeneratedCode
from src.core.ollama_client import OllamaClient


@pytest.fixture
def executor():
    """ExecutionAgent com OllamaClient mockado."""
    mock_ollama = MagicMock(spec=OllamaClient)
    return ExecutionAgent(mock_ollama)


def test_generated_code_schema_valido():
    """GeneratedCode deve aceitar dados válidos."""
    result = GeneratedCode(
        code="print('hello')",
        language="python",
        has_main=False,
        has_docstring=False,
        imports=[],
    )

    assert result.code == "print('hello')"
    assert result.language == "python"
    assert result.has_main is False


def test_generated_code_code_vazio_levanta_erro():
    """Código vazio deve levantar ValidationError."""
    with pytest.raises(ValidationError):
        GeneratedCode(code="", language="python")


def test_generated_code_language_invalida_levanta_erro():
    """Linguagem inválida deve levantar ValidationError."""
    with pytest.raises(ValidationError):
        GeneratedCode(code="x", language="javascript")


def test_parse_code_extrai_bloco_markdown(executor):
    """_parse_code deve extrair código do bloco Markdown."""
    raw = """
```python
#!/usr/bin/env python3
\"\"\"Script de backup\"\"\"

import os
import shutil

def main():
    pass

if __name__ == "__main__":
    main()
```
"""

    result = executor._parse_code(raw)

    assert "import os" in result.code
    assert "def main()" in result.code
    assert result.has_main is True
    assert result.has_docstring is True
    assert len(result.imports) == 2


def test_parse_code_fallback_em_codigo_vazio(executor):
    """Código vazio deve cair no fallback."""
    result = executor._parse_code("")

    assert "Erro na geração" in result.code
    assert result.has_main is False
    assert result.imports == []
