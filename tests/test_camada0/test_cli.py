"""Teste da CLI da Camada 0."""

from click.testing import CliRunner

from src.yby.cli import cli


def test_ask_sem_texto_falha() -> None:
    resultado = CliRunner().invoke(cli, ["ask"])

    assert resultado.exit_code != 0


def test_ask_com_texto_usa_provider_fake(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("YBY_DB_PATH", str(tmp_path / "yby.db"))
    monkeypatch.setenv("YBY_PROVEDOR", "fake")

    resultado = CliRunner().invoke(cli, ["ask", "crie um alerta de chuva"])

    assert resultado.exit_code == 0
    assert "Camada 0" in resultado.output
    assert "yby-fake" in resultado.output
