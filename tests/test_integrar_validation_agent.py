"""Testes para integração do ValidationAgent no fluxo completo."""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.main import cli
from src.core.ollama_client import OllamaConnectionError


@pytest.fixture
def runner():
    """Runner da CLI Click."""
    return CliRunner()


def test_fluxo_com_validacao_sucesso(runner):
    """Código válido deve passar na validação e ser exibido."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        json.dumps({
            "agent": "planning",
            "intent": "backup_automation",
            "confidence": 0.9,
            "requires_interview": True,
        }),
        "Primeira pergunta?",
        "PRD gerado",
        "```python\n#!/usr/bin/env python3\n\"\"\"Backup\"\"\"\n\nimport os\n\ndef main():\n    pass\n\nif __name__ == \"__main__\":\n    main()\n```",
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


def test_fluxo_com_validacao_falha_sintaxe(runner):
    """Código com erro de sintaxe deve falhar na validação."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        json.dumps({
            "agent": "planning",
            "intent": "backup_automation",
            "confidence": 0.9,
            "requires_interview": True,
        }),
        "Primeira pergunta?",
        "PRD gerado",
        "```python\ndef main(:\n    pass\n```",
    ]

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ), patch("builtins.input", return_value="resposta"):
        result = runner.invoke(
            cli,
            ["run", "--command", "Crie um script de backup"],
        )

    assert result.exit_code == 1


def test_fluxo_com_validacao_falha_seguranca(runner):
    """Código com padrão perigoso deve falhar na validação."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        json.dumps({
            "agent": "planning",
            "intent": "backup_automation",
            "confidence": 0.9,
            "requires_interview": True,
        }),
        "Primeira pergunta?",
        "PRD gerado",
        "```python\nimport subprocess\nsubprocess.run([\"ls\"])\n```",
    ]

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ), patch("builtins.input", return_value="resposta"):
        result = runner.invoke(
            cli,
            ["run", "--command", "Crie um script de backup"],
        )

    assert result.exit_code == 1


def test_fluxo_com_validacao_falha_estrutura(runner):
    """Código sem estrutura mínima deve falhar na validação."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        json.dumps({
            "agent": "planning",
            "intent": "backup_automation",
            "confidence": 0.9,
            "requires_interview": True,
        }),
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

    assert result.exit_code == 1


def test_fluxo_com_validacao_execution(runner):
    """Fluxo execution também deve validar código gerado."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        json.dumps({
            "agent": "execution",
            "intent": "chat_question",
            "confidence": 0.95,
            "requires_interview": False,
        }),
        "```python\n#!/usr/bin/env python3\n\"\"\"Resposta\"\"\"\n\nimport os\n\ndef main():\n    pass\n\nif __name__ == \"__main__\":\n    main()\n```",
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
