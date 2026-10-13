"""Testes unitários funcionais para o ExecutionAgent."""

from unittest.mock import MagicMock

import pytest

from src.agents.execution_agent import ExecutionAgent


@pytest.fixture
def ollama_mock():
    """Mock do OllamaClient."""
    return MagicMock()


@pytest.fixture
def executor(ollama_mock):
    """ExecutionAgent com Ollama simulado."""
    return ExecutionAgent(ollama=ollama_mock)


CODIGO_MARKDOWN = '''Aqui está o código:

```python
def main():
    print("Olá, YBY!")

if __name__ == "__main__":
    main()
```
'''

CODIGO_PURO = '''def main():
    print("Olá, YBY!")
'''


def test_extrai_codigo_de_markdown(executor, ollama_mock):
    """Deve extrair código de bloco ```python."""
    ollama_mock.generate.return_value = CODIGO_MARKDOWN

    codigo = executor.generate("PRD de teste")

    assert "def main():" in codigo
    assert "```" not in codigo
    ollama_mock.generate.assert_called_once()


def test_retorna_codigo_puro(executor, ollama_mock):
    """Deve retornar código puro quando não há bloco Markdown."""
    ollama_mock.generate.return_value = CODIGO_PURO

    codigo = executor.generate("PRD de teste")

    assert "def main():" in codigo


def test_generate_com_contexto(executor, ollama_mock):
    """Contexto adicional deve ser incluído no prompt."""
    ollama_mock.generate.return_value = CODIGO_PURO

    executor.generate("PRD de teste", context="Use pathlib")

    prompt_enviado = ollama_mock.generate.call_args.kwargs["prompt"]
    assert "Use pathlib" in prompt_enviado


def test_generate_com_rag(executor, ollama_mock):
    """Chunks RAG devem ser incluídos no contexto."""
    ollama_mock.generate.return_value = CODIGO_PURO

    executor.generate_with_rag(
        "PRD de teste",
        rag_chunks=["chunk 1", "chunk 2"]
    )

    prompt_enviado = ollama_mock.generate.call_args.kwargs["prompt"]
    assert "Chunk 1:" in prompt_enviado
    assert "Chunk 2:" in prompt_enviado
