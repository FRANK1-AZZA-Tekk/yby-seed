"""Vault de notas e a ausência de senha no código."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from src.agents.learning_agent import LearningAgent
from src.core.auto_cleanup import AutoCleanup
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


def test_reindex_detecta_edicao_externa_e_orfaos(tmp_path: Path) -> None:
    vault = Vault(tmp_path)
    vault.write_note("a", "alpha servidor")
    vault.write_note("b", "beta lista")
    # Edição fora do write_note (Syncthing / editor).
    (tmp_path / "a.md").write_text("alpha servidor atualizado hub", encoding="utf-8")
    (tmp_path / "c.md").write_text("gamma nova nota", encoding="utf-8")
    (tmp_path / "b.md").unlink()

    first = vault.reindex()
    assert first.added >= 1
    assert first.updated >= 1
    assert first.removed >= 1
    hits = vault.search("hub")
    assert hits and hits[0].name == "a.md"
    assert all(h.name != "b.md" for h in vault.search("lista"))

    second = vault.reindex()
    assert second.unchanged >= 2
    assert second.added == 0
    assert second.updated == 0
    assert second.removed == 0


def test_cli_reindex_e_recall_fresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YBY_VAULT_PATH", str(tmp_path))
    (tmp_path / "ext.md").write_text("nota externa syncthing hub", encoding="utf-8")
    runner = CliRunner()
    reindexed = runner.invoke(cli, ["reindex"])
    assert reindexed.exit_code == 0, reindexed.output
    assert "reindex ok" in reindexed.output

    fresh = runner.invoke(cli, ["recall", "--fresh", "hub"])
    assert fresh.exit_code == 0, fresh.output
    assert "ext.md" in fresh.output


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
    cleanup = AutoCleanup()
    assert agent.db_url == ""
    assert agent.conn is None
    assert cleanup.db_url == ""
    with pytest.raises(RuntimeError, match="YBY_DATABASE_URL"):
        agent.log_execution("x", {}, "print(1)", {})

    root = Path("src")
    for path in root.rglob("*.py"):
        assert "yby_seed_password" not in path.read_text(encoding="utf-8")
