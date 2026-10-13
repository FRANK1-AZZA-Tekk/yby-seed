"""Testes de integração para o fluxo completo com schemas Pydantic e RAG."""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.main import cli
from src.core.ollama_client import OllamaConnectionError
from src.agents.router_agent import RouterResult
from src.agents.planning_agent import PRD
from src.agents.execution_agent import GeneratedCode


@pytest.fixture
def runner():
    """Runner da CLI Click."""
    return CliRunner()


def test_fluxo_completo_planning_com_rag(runner):
    """Fluxo completo planning com RAG deve produzir PRD + código validados."""
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
        """# PRD: Backup de PDFs

## Objetivo
Automatizar backup de PDFs.

## Requisitos Funcionais
1. Listar PDFs
2. Copiar para backup

## Requisitos Não-Funcionais
- Executar diariamente

## Fluxo Principal
1. Escanejar pasta
2. Copiar arquivos

## Casos de Erro
- Pasta inexistente

## APIs Necessárias
- Nenhuma
""",
        "```python\n#!/usr/bin/env python3\n\"\"\"Backup\"\"\"\n\nimport os\n\ndef main():\n    pass\n\nif __name__ == \"__main__\":\n    main()\n```",
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
    assert "Backup de PDFs" in result.output
    assert "import os" in result.output
    mock_rag.retrieve.assert_called_once()


def test_fluxo_completo_execution_com_rag(runner):
    """Fluxo completo execution com RAG deve produzir resposta validada."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        json.dumps({
            "agent": "execution",
            "intent": "chat_question",
            "confidence": 0.95,
            "requires_interview": False,
        }),
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
    assert "resposta" in result.output
    mock_rag.retrieve.assert_called_once()


def test_fluxo_completo_planning_sem_rag(runner):
    """Fluxo completo planning sem RAG deve produzir PRD + código validados."""
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
        """# PRD: Backup de PDFs

## Objetivo
Automatizar backup de PDFs.

## Requisitos Funcionais
1. Listar PDFs

## Fluxo Principal
1. Escanejar pasta

## Casos de Erro
- Pasta inexistente
""",
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
    assert "Backup de PDFs" in result.output


def test_fluxo_completo_falha_router(runner):
    """Falha no Router deve interromper com exit 1."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True
    mock_ollama.generate.side_effect = OllamaConnectionError("offline")

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ):
        result = runner.invoke(
            cli,
            ["run", "--command", "Comando qualquer"],
        )

    assert result.exit_code == 1


def test_fluxo_completo_falha_planning(runner):
    """Falha no Planning deve interromper com exit 1."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        json.dumps({
            "agent": "planning",
            "intent": "backup_automation",
            "confidence": 0.9,
            "requires_interview": True,
        }),
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


def test_fluxo_completo_falha_execution(runner):
    """Falha no Execution deve interromper com exit 1."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.side_effect = [
        json.dumps({
            "agent": "execution",
            "intent": "chat_question",
            "confidence": 0.95,
            "requires_interview": False,
        }),
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


def test_fluxo_completo_falha_rag(runner):
    """Falha no RAG deve interromper com exit 1."""
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


def test_fluxo_completo_agente_desconhecido(runner):
    """Agente desconhecido deve falhar com exit 1."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True

    mock_ollama.generate.return_value = json.dumps({
        "agent": "desconhecido",
        "intent": "x",
        "confidence": 0.5,
        "requires_interview": False,
    })

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ):
        result = runner.invoke(
            cli,
            ["run", "--command", "Comando qualquer"],
        )

    assert result.exit_code == 1
