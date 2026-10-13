"""Testes para o run mínimo integrando RouterAgent."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.main import cli
from src.core.ollama_client import OllamaConnectionError


@pytest.fixture
def runner():
    """Runner da CLI Click."""
    return CliRunner()


def test_run_classifica_e_roteia(runner):
    """Run deve classificar comando e imprimir roteamento."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True
    mock_ollama.generate.return_value = (
        '{"agent": "planning", "intent": "backup_automation", '
        '"confidence": 0.9, "requires_interview": true}'
    )

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ):
        result = runner.invoke(
            cli,
            ["run", "--command", "Crie um script de backup"],
        )

    assert result.exit_code == 0
    assert "agent=planning" in result.output
    assert "intent=backup_automation" in result.output
    assert "confidence=0.9" in result.output
    assert "requires_interview=True" in result.output


def test_run_falha_se_ollama_offline(runner):
    """Run deve falhar se Ollama não estiver acessível."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = False

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ):
        result = runner.invoke(
            cli,
            ["run", "--command", "Olá"],
        )

    assert result.exit_code == 1


def test_run_falha_se_router_levantar_erro(runner):
    """Run deve falhar graciosamente se RouterAgent levantar erro."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True
    mock_ollama.generate.side_effect = OllamaConnectionError("offline")

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ):
        result = runner.invoke(
            cli,
            ["run", "--command", "Olá"],
        )

    assert result.exit_code == 1


def test_run_exige_comando(runner):
    """Run deve exigir --command."""
    result = runner.invoke(cli, ["run"])

    assert result.exit_code != 0
    assert "--command" in result.output
