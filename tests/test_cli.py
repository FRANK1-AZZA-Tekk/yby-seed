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
    assert "Não implementado: run" in result.output
    assert "brief" in result.output
    assert "Qdrant" in result.output


def test_run_nao_mente_sucesso():
    runner = CliRunner()
    result = runner.invoke(cli, ["run"])
    assert result.exit_code == 2
    assert "ainda não inicia" in result.output
