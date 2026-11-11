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
