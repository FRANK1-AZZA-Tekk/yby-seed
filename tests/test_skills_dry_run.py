"""Testes da Camada C — skills em dry-run, sem execução de código."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from src.skills.cli import skills
from src.skills.dry_run import (
    AutoRunRefused,
    SkillsDryRun,
    refuse_auto_run,
    request_human_confirm,
)


def _write_skill(root: Path, name: str, description: str = "Skill de teste") -> Path:
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n"
        "compatibility: python\nlicense: MIT\n---\n\nBody.\n",
        encoding="utf-8",
    )
    return skill_dir


def test_discover_lists_skills(tmp_path: Path):
    _write_skill(tmp_path, "backup-automation", "Backup de arquivos")
    _write_skill(tmp_path, "file-operations", "Operações com arquivos")

    layer = SkillsDryRun(tmp_path / "skills")
    found = layer.discover()

    assert [item.name for item in found] == ["backup-automation", "file-operations"]
    assert found[0].description == "Backup de arquivos"


def test_discover_empty_directory(tmp_path: Path):
    (tmp_path / "skills").mkdir()
    layer = SkillsDryRun(tmp_path / "skills")
    assert layer.discover() == []


def test_preview_is_dry_run(tmp_path: Path):
    _write_skill(tmp_path, "demo-skill")
    layer = SkillsDryRun(tmp_path / "skills")

    preview = layer.preview("demo-skill", request="backup dos PDFs")

    assert preview.would_execute is False
    assert preview.skill.name == "demo-skill"
    assert "backup dos PDFs" in preview.steps[1]
    assert "nenhum código seria executado" in preview.message


def test_preview_unknown_skill(tmp_path: Path):
    (tmp_path / "skills").mkdir()
    layer = SkillsDryRun(tmp_path / "skills")
    with pytest.raises(KeyError):
        layer.preview("nao-existe")


def test_refuse_auto_run():
    with pytest.raises(AutoRunRefused):
        refuse_auto_run("backup-automation")


def test_request_human_confirm_refuses_auto():
    assert request_human_confirm(auto=True, skill_name="x") is False
    assert request_human_confirm(auto=False, skill_name="x") is False


def test_cli_lists_skills(tmp_path: Path):
    _write_skill(tmp_path, "backup-automation", "Backup de arquivos")
    runner = CliRunner()
    result = runner.invoke(
        skills,
        ["list", "--skills-dir", str(tmp_path / "skills")],
    )
    assert result.exit_code == 0
    assert "backup-automation" in result.output
    assert "confirmação humana" in result.output


def test_cli_preview_dry_run(tmp_path: Path):
    _write_skill(tmp_path, "demo-skill")
    runner = CliRunner()
    result = runner.invoke(
        skills,
        [
            "preview",
            "demo-skill",
            "backup dos PDFs",
            "--skills-dir",
            str(tmp_path / "skills"),
        ],
    )
    assert result.exit_code == 0
    assert "DRY-RUN" in result.output
    assert "nenhum código seria executado" in result.output


def test_cli_preview_unknown_skill(tmp_path: Path):
    (tmp_path / "skills").mkdir()
    runner = CliRunner()
    result = runner.invoke(
        skills,
        ["preview", "nao-existe", "--skills-dir", str(tmp_path / "skills")],
    )
    assert result.exit_code == 2
    assert "não encontrada" in result.output