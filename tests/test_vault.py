"""Vault de notas e a ausência de senha no código."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from src.agents.learning_agent import LearningAgent
from src.main import cli
from src.memory.vault import Vault, VaultError


def test_nota_e_busca(tmp_path: Path) -> None:
    vault = Vault(tmp_path)
    vault.write_note("diario", "o servidor de casa guarda as notas do YBY")
    vault.write_note("outra", "lista de compras")

    text = vault.read_note("diario")
    assert "servidor de casa" in text
    hits = vault.search("servidor de casa")
    assert hits
    assert hits[0].name == "diario.md"


def test_nota_nao_escapa_do_vault(tmp_path: Path) -> None:
    vault = Vault(tmp_path)
    with pytest.raises(VaultError):
        vault.write_note("../fora", "não")


def test_cli_grava_no_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YBY_VAULT_PATH", str(tmp_path))
    result = CliRunner().invoke(cli, ["note", "ideia", "memória local"])
    assert result.exit_code == 0
    assert (tmp_path / "ideia.md").read_text(encoding="utf-8").startswith("memória")


def test_agentes_nao_trazem_senha(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YBY_DATABASE_URL", raising=False)
    agent = LearningAgent()
    assert agent.db_url == ""
    assert agent.conn is None
    with pytest.raises(RuntimeError, match="YBY_DATABASE_URL"):
        agent.log_execution("x", {}, "print(1)", {})

    root = Path("src")
    for path in root.rglob("*.py"):
        assert "yby_seed_password" not in path.read_text(encoding="utf-8")
