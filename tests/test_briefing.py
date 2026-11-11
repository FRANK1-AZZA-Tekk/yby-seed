"""Testes do briefing revisável (Fase 1) — Ollama mockado."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from pydantic import ValidationError
from src.agents.briefing_pipeline import BriefingPipeline
from src.core.briefing import Briefing, briefing_to_markdown, export_briefing
from src.core.ollama_client import OllamaError
from src.main import cli


def _valid_briefing_json() -> str:
    return json.dumps(
        {
            "title": "Backup diário",
            "summary": "Automatizar backup de documentos para disco externo.",
            "requirements": ["Copiar ~/Documentos", "Agendar diariamente"],
            "assumptions": ["Disco externo montado em /mnt/backup"],
            "open_questions": ["Manter versões antigas?"],
            "tasks": ["Definir pasta origem", "Escolher destino", "Revisar agendamento"],
        },
        ensure_ascii=False,
    )


def test_briefing_model_validate_and_coerce():
    briefing = Briefing(
        title="  Título  ",
        summary=" Resumo ",
        requirements="único requisito",
        assumptions=[],
        open_questions=None,
        tasks=["a", " ", "b"],
        source_request="Quero X",
    )
    assert briefing.title == "Título"
    assert briefing.summary == "Resumo"
    assert briefing.requirements == ["único requisito"]
    assert briefing.open_questions == []
    assert briefing.tasks == ["a", "b"]
    assert briefing.approved is False


def test_briefing_rejects_empty_title():
    with pytest.raises(ValidationError):
        Briefing(title="  ", summary="ok")


def test_export_markdown_and_json(tmp_path: Path):
    briefing = Briefing(
        title="Backup diário",
        summary="Resumo do backup",
        requirements=["req1"],
        assumptions=["assump1"],
        open_questions=["q1"],
        tasks=["task1"],
        source_request="Quero backup",
        approved=True,
    )
    md_path, json_path = export_briefing(briefing, tmp_path)
    assert md_path.exists() and json_path.exists()
    md = md_path.read_text(encoding="utf-8")
    assert "# Backup diário" in md
    assert "Nenhuma execução automática de código." in md
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["title"] == "Backup diário"
    assert data["tasks"] == ["task1"]
    assert data["approved"] is True


def test_briefing_to_markdown_lists_empty_sections():
    text = briefing_to_markdown(
        Briefing(title="T", summary="S", requirements=[], assumptions=[], open_questions=[], tasks=[])
    )
    assert "(nenhum)" in text


def test_create_from_answers_mocked_ollama():
    ollama = MagicMock()
    # interview_from_answers (basic, 1 answer): first_q + prd
    # depois _structure_from_prd: 1 generate
    ollama.generate.side_effect = [
        "Qual pasta de origem?",
        "# PRD\n## Objetivo\nBackup\n",
        _valid_briefing_json(),
    ]
    pipeline = BriefingPipeline(ollama=ollama, owns_client=False)
    briefing = pipeline.create_from_answers(
        "Quero backup",
        answers=["~/Documentos"],
        mode="basic",
    )
    assert briefing.title == "Backup diário"
    assert "Copiar ~/Documentos" in briefing.requirements
    assert briefing.source_request == "Quero backup"
    assert briefing.approved is False
    assert ollama.generate.call_count == 3
    pipeline.close()


def test_create_from_answers_empty_request():
    pipeline = BriefingPipeline(ollama=MagicMock(), owns_client=False)
    with pytest.raises(ValueError, match="vazio"):
        pipeline.create_from_answers("  ", [])


def test_create_from_answers_ollama_error():
    ollama = MagicMock()
    ollama.generate.side_effect = OllamaError("down")
    pipeline = BriefingPipeline(ollama=ollama, owns_client=False)
    with pytest.raises(OllamaError):
        pipeline.create_from_answers("Quero X", ["a"], mode="basic")


def test_pipeline_export_writes_files(tmp_path: Path):
    ollama = MagicMock()
    ollama.generate.side_effect = [
        "Pergunta?",
        "# PRD",
        _valid_briefing_json(),
    ]
    pipeline = BriefingPipeline(ollama=ollama, owns_client=False)
    briefing = pipeline.create_from_answers("Quero backup", ["~/docs"], mode="basic")
    briefing.approved = True
    md_path, json_path = pipeline.export(briefing, tmp_path)
    assert md_path.parent == tmp_path
    assert json_path.suffix == ".json"
    assert "Backup diário" in md_path.read_text(encoding="utf-8")


def test_cli_brief_noninteractive(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = Briefing(
        title="Backup diário",
        summary="Resumo",
        requirements=["r1"],
        assumptions=[],
        open_questions=[],
        tasks=["t1"],
        source_request="Quero backup",
        approved=True,
    )

    class FakePipeline:
        def __init__(self, *args, **kwargs):
            pass

        def create_from_answers(self, request, answers, *, mode="basic"):
            assert request == "Quero backup"
            assert answers == ["~/Documentos", "/mnt/backup"]
            assert mode == "basic"
            return fake.model_copy()

        def export(self, briefing, output_dir=None, *, project_root=None):
            return export_briefing(briefing, tmp_path / "out")

        def close(self):
            return None

    monkeypatch.setattr("src.agents.briefing_pipeline.BriefingPipeline", FakePipeline)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "brief",
            "--request",
            "Quero backup",
            "--answer",
            "~/Documentos",
            "--answer",
            "/mnt/backup",
            "--approve",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Exportado:" in result.output
    assert "Nenhuma execução automática de código." in result.output
    assert list((tmp_path / "out").glob("*.md"))
    assert list((tmp_path / "out").glob("*.json"))


def test_cli_brief_requires_request_with_answers():
    runner = CliRunner()
    result = runner.invoke(cli, ["brief", "--answer", "só resposta"])
    assert result.exit_code == 2
    assert "--request" in result.output


def test_status_menciona_brief():
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "brief" in result.output
