"""Testes da CLI honesta do YBY SEED."""

from click.testing import CliRunner
from src.main import cli


def test_doctor_ok():
    runner = CliRunner()
    result = runner.invoke(cli, ["doctor"])
    assert result.exit_code == 0
    assert "Doctor OK" in result.output


def test_status_descreve_estado_real():
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "Skills mode: dry_run" in result.output
    assert "Forma do produto" in result.output
    assert "brief" in result.output.lower()
    assert "Não implementado: skills exec" in result.output


def test_run_inicia_repl_e_encerra_com_quit():
    runner = CliRunner()
    result = runner.invoke(cli, ["run"], input="quit\n")
    assert result.exit_code == 0
    assert "Function Over Form" in result.output


def test_skills_lista_e_recusa_run():
    runner = CliRunner()
    listed = runner.invoke(cli, ["skills"])
    assert listed.exit_code == 0
    assert "backup-automation" in listed.output
    refused = runner.invoke(cli, ["skills", "backup-automation", "--run"])
    assert refused.exit_code == 2
    assert "recusada" in refused.output.lower() or "ERRO" in refused.output
