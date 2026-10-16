from pathlib import Path

from src.skills.skill_manager import Skill, SkillManager, SkillMetadata


SKILL_MD = """---
name: backup
description: Fazer backup dos arquivos
compatibility: yby-mvp
license: MIT
---

## Quando Usar
Quando o usuario pedir backup

## Exemplos
Fazer backup dos meus arquivos
"""


def _make_skill(directory=None):
    metadata = SkillMetadata(
        name="backup",
        description="Fazer backup dos arquivos",
        directory=directory,
    )
    return Skill(metadata, SKILL_MD)


def test_metadata_from_yaml(tmp_path):
    yaml_str = SKILL_MD.split("---")[1].strip()
    metadata = SkillMetadata.from_yaml(yaml_str, tmp_path)

    assert metadata.name == "backup"
    assert metadata.description == "Fazer backup dos arquivos"
    assert metadata.compatibility == "yby-mvp"
    assert metadata.license == "MIT"
    assert metadata.directory == tmp_path


def test_skill_parses_instructions():
    skill = _make_skill()

    assert "quando usar" in skill.instructions
    assert "backup" in skill.get_instructions()
    assert "Fazer backup dos meus arquivos" in skill.get_examples()


def test_should_activate_with_matching_command():
    skill = _make_skill()

    assert skill.should_activate("Fazer backup dos meus arquivos") is True


def test_should_activate_with_unrelated_command():
    skill = _make_skill()

    assert skill.should_activate("Qual e a capital da Franca") is False


def test_get_scripts_without_scripts_dir(tmp_path):
    skill = _make_skill(directory=tmp_path)

    assert skill.get_scripts() == []


def test_manager_discovers_skill(tmp_path):
    skill_dir = tmp_path / "backup"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")

    manager = SkillManager(skills_dir=str(tmp_path))
    manager.discover_skills()

    assert "backup" in manager.skills
    assert manager.list_skills()[0]["name"] == "backup"


def test_manager_finds_best_skill(tmp_path):
    skill_dir = tmp_path / "backup"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")

    manager = SkillManager(skills_dir=str(tmp_path))
    manager.discover_skills()

    best = manager.find_best_skill("Fazer backup dos meus arquivos")

    assert best is not None
    assert best.metadata.name == "backup"


def test_manager_with_empty_directory(tmp_path):
    manager = SkillManager(skills_dir=str(tmp_path))
    manager.discover_skills()

    assert manager.skills == {}
    assert manager.find_best_skill("Fazer backup dos meus arquivos") is None


def test_manager_with_missing_directory(tmp_path):
    manager = SkillManager(skills_dir=str(tmp_path / "nao_existe"))
    manager.discover_skills()

    assert manager.skills == {}
