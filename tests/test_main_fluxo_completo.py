"""Testes para o fluxo completo Router → Planning/Execution."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.main import cli
from src.core.ollama_client import OllamaConnectionError


@pytest.fixture
def runner():
    """Runner da CLI Click."""
    return CliRunner()


def test_fluxo_completo_planning(runner):
    """Comando planning deve chamar PlanningAgent e ExecutionAgent."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    # RouterAgent retorna planning
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


def test_fluxo_completo_execution(runner):
    """Comando execution deve chamar ExecutionAgent diretamente."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        '{"agent": "execution", "intent": "chat_question", '
        '"confidence": 0.95, "requires_interview": false}',
        "```python\nprint('resposta')\n```",
    ]

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ):
        result = runner.invoke(
            cli,
            ["run", "--command", "Como fazer backup?"],
        )

    assert result.exit_code == 0
    assert "--- RESPOSTA ---" in result.output


def test_fluxo_falha_se_planning_levantar_erro(runner):
    """Falha no PlanningAgent deve interromper com exit 1."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        '{"agent": "planning", "intent": "backup_automation", '
        '"confidence": 0.9, "requires_interview": true}',
        OllamaConnectionError("offline"),
    ]

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ):
        result = runner.invoke(
            cli,
            ["run", "--command", "Crie um script de backup"],
        )

    assert result.exit_code == 1


def test_fluxo_falha_se_execution_levantar_erro(runner):
    """Falha no ExecutionAgent deve interromper com exit 1."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        '{"agent": "execution", "intent": "chat_question", '
        '"confidence": 0.95, "requires_interview": false}',
        OllamaConnectionError("offline"),
    ]

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ):
        result = runner.invoke(
            cli,
            ["run", "--command", "Como fazer backup?"],
        )

    assert result.exit_code == 1


def test_fluxo_agente_desconhecido(runner):
    """Agente desconhecido deve falhar com exit 1."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.return_value = (
        '{"agent": "desconhecido", "intent": "x", '
        '"confidence": 0.5, "requires_interview": false}'
    )

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ):
        result = runner.invoke(
            cli,
            ["run", "--command", "Comando qualquer"],
        )

    assert result.exit_code == 1
