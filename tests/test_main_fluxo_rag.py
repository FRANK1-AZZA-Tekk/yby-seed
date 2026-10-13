"""Testes para o fluxo com RAG integrado."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.main import cli
from src.core.ollama_client import OllamaConnectionError


@pytest.fixture
def runner():
    """Runner da CLI Click."""
    return CliRunner()


def test_fluxo_com_rag_planning(runner):
    """Comando planning com --rag deve chamar generate_with_rag."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        '{"agent": "planning", "intent": "backup_automation", '
        '"confidence": 0.9, "requires_interview": true}',
        "Primeira pergunta?",
        "PRD gerado",
        "```python\nprint('hello')\n```",
    ]

    mock_rag = MagicMock()
    mock_rag.retrieve.return_value = ["chunk1", "chunk2"]

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ), patch(
        "src.main.RAGOptimizer", return_value=mock_rag
    ), patch("builtins.input", return_value="resposta"):
        result = runner.invoke(
            cli,
            ["run", "--command", "Crie um script de backup", "--rag"],
        )

    assert result.exit_code == 0
    assert "--- PRD ---" in result.output
    assert "--- CÓDIGO ---" in result.output
    mock_rag.retrieve.assert_called_once()


def test_fluxo_com_rag_execution(runner):
    """Comando execution com --rag deve chamar generate_with_rag."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        '{"agent": "execution", "intent": "chat_question", '
        '"confidence": 0.95, "requires_interview": false}',
        "```python\nprint('resposta')\n```",
    ]

    mock_rag = MagicMock()
    mock_rag.retrieve.return_value = ["chunk1"]

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ), patch(
        "src.main.RAGOptimizer", return_value=mock_rag
    ):
        result = runner.invoke(
            cli,
            ["run", "--command", "Como fazer backup?", "--rag"],
        )

    assert result.exit_code == 0
    assert "--- RESPOSTA ---" in result.output
    mock_rag.retrieve.assert_called_once()


def test_fluxo_sem_rag_planning(runner):
    """Comando planning sem --rag deve chamar generate normal."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        '{"agent": "planning", "intent": "backup_automation", '
        '"confidence": 0.9, "requires_interview": true}',
        "Primeira pergunta?",
        "PRD gerado",
        "```python\nprint('hello')\n```",
    ]

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ), patch("builtins.input", return_value="resposta"):
        result = runner.invoke(
            cli,
            ["run", "--command", "Crie um script de backup"],
        )

    assert result.exit_code == 0
    assert "--- PRD ---" in result.output
    assert "--- CÓDIGO ---" in result.output


def test_fluxo_rag_falha_se_rag_levantar_erro(runner):
    """Falha no RAG deve interromper com exit 1."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        '{"agent": "planning", "intent": "backup_automation", '
        '"confidence": 0.9, "requires_interview": true}',
        "Primeira pergunta?",
        "PRD gerado",
    ]

    mock_rag = MagicMock()
    mock_rag.retrieve.side_effect = OllamaConnectionError("offline")

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ), patch(
        "src.main.RAGOptimizer", return_value=mock_rag
    ), patch("builtins.input", return_value="resposta"):
        result = runner.invoke(
            cli,
            ["run", "--command", "Crie um script de backup", "--rag"],
        )

    assert result.exit_code == 1
