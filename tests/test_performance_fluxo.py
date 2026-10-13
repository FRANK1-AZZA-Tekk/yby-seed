"""Testes de performance para o fluxo completo."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.main import cli


@pytest.fixture
def runner():
    """Runner da CLI Click."""
    return CliRunner()


def test_performance_router_classify(runner):
    """RouterAgent.classify deve responder em menos de 1s (mockado)."""
    mock_ollama = MagicMock()
    mock_ollama.is_healthy.return_value = True
    mock_ollama.generate.return_value = json.dumps({
        "agent": "planning",
        "intent": "backup_automation",
        "confidence": 0.9,
        "requires_interview": True,
    })

    start = time.time()

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ):
        result = runner.invoke(
            cli,
            ["run", "--command", "Crie um script de backup"],
        )

    elapsed = time.time() - start

    assert result.exit_code == 0
    assert elapsed < 1.0, f"Router demorou {elapsed:.2f}s (limite: 1s)"


def test_performance_fluxo_planning_sem_rag(runner):
    """Fluxo planning sem RAG deve responder em menos de 2s (mockado)."""
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

    start = time.time()

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ), patch("builtins.input", return_value="resposta"):
        result = runner.invoke(
            cli,
            ["run", "--command", "Crie um script de backup"],
        )

    elapsed = time.time() - start

    assert result.exit_code == 0
    assert elapsed < 2.0, f"Fluxo planning demorou {elapsed:.2f}s (limite: 2s)"


def test_performance_fluxo_planning_com_rag(runner):
    """Fluxo planning com RAG deve responder em menos de 3s (mockado)."""
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

    mock_rag = MagicMock()
    mock_rag.retrieve.return_value = ["chunk1", "chunk2", "chunk3"]

    start = time.time()

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ), patch(
        "src.main.RAGOptimizer", return_value=mock_rag
    ), patch("builtins.input", return_value="resposta"):
        result = runner.invoke(
            cli,
            ["run", "--command", "Crie um script de backup", "--rag"],
        )

    elapsed = time.time() - start

    assert result.exit_code == 0
    assert elapsed < 3.0, f"Fluxo planning+RAG demorou {elapsed:.2f}s (limite: 3s)"


def test_performance_fluxo_execution_com_rag(runner):
    """Fluxo execution com RAG deve responder em menos de 2s (mockado)."""
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

    start = time.time()

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ), patch(
        "src.main.RAGOptimizer", return_value=mock_rag
    ):
        result = runner.invoke(
            cli,
            ["run", "--command", "Como fazer backup?", "--rag"],
        )

    elapsed = time.time() - start

    assert result.exit_code == 0
    assert elapsed < 2.0, f"Fluxo execution+RAG demorou {elapsed:.2f}s (limite: 2s)"


def test_performance_validacao_seguranca():
    """CodeSafetyValidator deve validar em menos de 100ms."""
    from src.security.code_safety_validator import CodeSafetyValidator

    validator = CodeSafetyValidator()
    code = """
import os
import shutil

def main():
    print("hello")
    for i in range(100):
        print(i)

if __name__ == "__main__":
    main()
"""

    start = time.time()
    result = validator.validate(code)
    elapsed = time.time() - start

    assert result.is_safe is True
    assert elapsed < 0.1, f"Validação demorou {elapsed:.3f}s (limite: 100ms)"


def test_performance_fluxo_completo_stress(runner):
    """Fluxo completo deve suportar 10 execuções consecutivas em menos de 10s."""
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
    ] * 10

    start = time.time()

    with patch(
        "src.main.OllamaClient", return_value=mock_ollama
    ):
        for _ in range(10):
            result = runner.invoke(
                cli,
                ["run", "--command", "Como fazer backup?"],
            )
            assert result.exit_code == 0

    elapsed = time.time() - start

    assert elapsed < 10.0, f"10 execuções demoraram {elapsed:.2f}s (limite: 10s)"
