"""Testes para integração do GovernanceAgent no fluxo completo."""

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


def test_fluxo_com_governanca_aprovado(runner):
    """Código seguro deve passar na governança e ser exibido."""
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
        "```python\n#!/usr/bin/env python3\n\"\"\"Backup\"\"\"\n\nimport json\nimport zipfile\n\ndef main():\n    pass\n\nif __name__ == \"__main__\":\n    main()\n```",
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


def test_fluxo_com_governanca_bloqueado_import(runner):
    """Import não permitido deve bloquear pela governança."""
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

    assert result.exit_code == 1


def test_fluxo_com_governanca_bloqueado_padrao_perigoso(runner):
    """Padrão perigoso deve bloquear pela governança."""
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
        "```python\n#!/usr/bin/env python3\n\"\"\"Backup\"\"\"\n\nimport os\n\ndef main():\n    os.system(\"rm -rf /\")\n\nif __name__ == \"__main__\":\n    main()\n```",
    ]

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ), patch("builtins.input", return_value="resposta"):
        result = runner.invoke(
            cli,
            ["run", "--command", "Crie um script de backup"],
        )

    assert result.exit_code == 1


def test_fluxo_com_governanca_acao_critica(runner):
    """Ação crítica deve exigir aprovação humana e bloquear."""
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
        "```python\n#!/usr/bin/env python3\n\"\"\"Backup\"\"\"\n\nimport json\nimport zipfile\n\ndef main():\n    pass\n\nif __name__ == \"__main__\":\n    main()\n```",
    ]

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ), patch("builtins.input", return_value="resposta"):
        result = runner.invoke(
            cli,
            [
                "run",
                "--command",
                "Crie um script de backup",
                "--action",
                "delete_files",
            ],
        )

    assert result.exit_code == 1


def test_fluxo_com_governanca_execution(runner):
    """Fluxo execution também deve passar pela governança."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        json.dumps({
            "agent": "execution",
            "intent": "chat_question",
            "confidence": 0.95,
            "requires_interview": False,
        }),
        "```python\n#!/usr/bin/env python3\n\"\"\"Resposta\"\"\"\n\nimport json\n\ndef main():\n    pass\n\nif __name__ == \"__main__\":\n    main()\n```",
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
