"""Testes para validação Pydantic no PlanningAgent."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from src.agents.planning_agent import PlanningAgent, PRD
from src.core.ollama_client import OllamaClient


@pytest.fixture
def planner():
    """PlanningAgent com OllamaClient mockado."""
    mock_ollama = MagicMock(spec=OllamaClient)
    return PlanningAgent(mock_ollama)


def test_prd_schema_valido():
    """PRD deve aceitar dados válidos."""
    prd = PRD(
        title="Backup de PDFs",
        objective="Automatizar backup de PDFs",
        functional_requirements=["Listar PDFs", "Copiar para backup"],
        non_functional_requirements=["Executar diariamente"],
        main_flow=["Escanejar pasta", "Copiar arquivos"],
        error_cases=["Pasta inexistente"],
        required_apis=["Nenhuma"],
    )

    assert prd.title == "Backup de PDFs"
    assert len(prd.functional_requirements) == 2
    assert len(prd.main_flow) == 2


def test_prd_title_vazio_levanta_erro():
    """Título vazio deve levantar ValidationError."""
    with pytest.raises(ValidationError):
        PRD(title="", objective="x")


def test_prd_objective_vazio_levanta_erro():
    """Objetivo vazio deve levantar ValidationError."""
    with pytest.raises(ValidationError):
        PRD(title="x", objective="")


def test_parse_prd_extrai_secoes(planner):
    """_parse_prd deve extrair seções do Markdown."""
    raw = """
# PRD: Backup de PDFs

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
"""

    prd = planner._parse_prd(raw, "fallback")

    assert prd.title == "Backup de PDFs"
    assert prd.objective == "Automatizar backup de PDFs."
    assert len(prd.functional_requirements) == 2
    assert len(prd.non_functional_requirements) == 1
    assert len(prd.main_flow) == 2
    assert len(prd.error_cases) == 1
    assert len(prd.required_apis) == 1


def test_parse_prd_fallback_em_markdown_invalido(planner):
    """Markdown inválido deve cair no fallback."""
    prd = planner._parse_prd("texto sem estrutura", "Comando original")

    assert prd.title == "Comando original"
    assert prd.objective == "Objetivo não especificado"
    assert prd.functional_requirements == []
