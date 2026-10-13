"""Testes unitários funcionais para o PlanningAgent."""

from unittest.mock import MagicMock

import pytest

from src.agents.planning_agent import PlanningAgent


@pytest.fixture
def ollama_mock():
    """Mock do OllamaClient."""
    return MagicMock()


@pytest.fixture
def planner(ollama_mock):
    """PlanningAgent com Ollama simulado."""
    return PlanningAgent(ollama=ollama_mock)


def test_gera_primeira_pergunta(planner, ollama_mock):
    """Deve gerar a primeira pergunta da entrevista."""
    ollama_mock.generate.return_value = "Quais PDFs você quer organizar?"

    pergunta = planner._generate_first_question("Quero organizar PDFs")

    assert pergunta == "Quais PDFs você quer organizar?"
    ollama_mock.generate.assert_called_once()


def test_gera_proxima_pergunta(planner, ollama_mock):
    """Deve gerar próxima pergunta quando não finaliza."""
    ollama_mock.generate.return_value = "Qual pasta de origem?"

    historico = [
        {"role": "user", "content": "Quero organizar PDFs"},
        {"role": "assistant", "content": "Quais PDFs?"},
        {"role": "user", "content": "Os da pasta Downloads"},
    ]

    pergunta = planner._generate_next_question(historico, "junior")

    assert pergunta == "Qual pasta de origem?"


def test_finaliza_quando_ollama_diz_finalizar(planner, ollama_mock):
    """Deve retornar None quando o Ollama indica FINALIZAR."""
    ollama_mock.generate.return_value = "FINALIZAR"

    historico = [
        {"role": "user", "content": "Quero organizar PDFs"},
    ]

    resultado = planner._generate_next_question(historico, "basic")

    assert resultado is None


def test_gera_prd(planner, ollama_mock):
    """Deve gerar PRD em markdown."""
    ollama_mock.generate.return_value = (
        "# PRD: Organizar PDFs\n\n## Objetivo\nOrganizar PDFs por assunto.\n"
    )

    historico = [
        {"role": "user", "content": "Quero organizar PDFs"},
    ]

    prd = planner._generate_prd(historico, "Quero organizar PDFs")

    assert prd.startswith("# PRD:")
    assert "Objetivo" in prd
    ollama_mock.generate.assert_called_once()


def test_modos_definem_max_perguntas(planner, ollama_mock, monkeypatch):
    """Modo basic deve limitar a 2 perguntas na entrevista."""
    respostas = iter([
        "Primeira pergunta?",
        "FINALIZAR",
        "# PRD: Teste\n",
    ])
    ollama_mock.generate.side_effect = lambda **kwargs: next(respostas)

    monkeypatch.setattr("builtins.input", lambda _: "resposta do usuário")

    prd = planner.interview("Quero organizar PDFs", mode="basic")

    assert prd.startswith("# PRD:")
