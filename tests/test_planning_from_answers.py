"""Testes do caminho não-interativo do PlanningAgent."""

from unittest.mock import MagicMock

from src.agents.planning_agent import PlanningAgent


def test_interview_from_answers_gera_prd():
    ollama = MagicMock()
    ollama.generate.side_effect = [
        "Qual pasta de origem?",
        "# PRD: Backup\n\n## Objetivo\nBackup diário\n",
    ]
    planner = PlanningAgent(ollama=ollama)
    prd = planner.interview_from_answers(
        "Quero backup",
        answers=["~/Documentos"],
        mode="basic",
    )
    assert "PRD" in prd
    assert ollama.generate.call_count == 2


def test_max_questions_for():
    planner = PlanningAgent(ollama=MagicMock())
    assert planner.max_questions_for("basic") == 2
    assert planner.max_questions_for("junior") == 5
    assert planner.max_questions_for("pro") == 15
