"""Testes do sistema seguro de skills."""

import pytest
from click.testing import CliRunner

from src.core.skills import list_skills, run_skill
from src.main import cli


runner = CliRunner()


def test_list_skills_returns_registered_skills():
    names = [skill.name for skill in list_skills()]
    assert "echo" in names
    assert "read_doc" in names


def test_run_echo_skill():
    assert run_skill("echo", {"message": "olá"}) == "olá"


def test_unknown_skill_fails():
    with pytest.raises(KeyError):
        run_skill("inexistente")


def test_cli_lists_skills():
    result = runner.invoke(cli, ["skills", "list"])
    assert result.exit_code == 0
    assert "echo" in result.output
    assert "read_doc" in result.output


def test_cli_runs_echo_skill():
    result = runner.invoke(cli, ["skills", "run", "echo", "--arg", "message=olá"])
    assert result.exit_code == 0
    assert result.output.strip() == "olá"


def test_cli_rejects_unknown_skill():
    result = runner.invoke(cli, ["skills", "run", "inexistente"])
    assert result.exit_code == 1
