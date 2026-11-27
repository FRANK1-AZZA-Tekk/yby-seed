"""Vault de notas e a ausência de senha no código."""

import os
import time
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


def test_indice_usa_escrita_atomica(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = Vault(tmp_path)
    replaces: list[tuple[str, str]] = []
    real_replace = os.replace

    def _spy(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        replaces.append((str(src), str(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", _spy)
    vault.write_note("atomica", "corpo seguro")
    assert replaces
    note_path = tmp_path / "atomica.md"
    assert any(dst == str(note_path) for _src, dst in replaces)
    assert replaces[-1][1] == str(vault.index_path)
    assert vault.index_path.is_file()
    assert note_path.is_file()
    assert note_path.read_text(encoding="utf-8") == "corpo seguro"


def test_busca_enxerga_nota_editada_fora_do_write(tmp_path: Path) -> None:
    vault = Vault(tmp_path)
    vault.write_note("diario", "assunto antigo")
    (tmp_path / "manual.md").write_text("servidor de casa na nota manual\n", encoding="utf-8")
    note = tmp_path / "diario.md"
    note.write_text("o servidor de casa foi atualizado\n", encoding="utf-8")
    stamp = time.time() + 5
    os.utime(note, (stamp, stamp))
    (tmp_path / "sumiu.md").write_text("nao deve aparecer\n", encoding="utf-8")
    vault.write_note("sumiu", "nao deve aparecer")
    (tmp_path / "sumiu.md").unlink()

    names = [hit.name for hit in vault.search("servidor de casa")]
    assert "manual.md" in names
    assert "diario.md" in names
    assert all(name != "sumiu.md" for name in vault.search("aparecer"))


def test_nota_nao_escapa_do_vault(tmp_path: Path) -> None:
    vault = Vault(tmp_path)
    with pytest.raises(VaultError):
        vault.write_note("../fora", "não")


def test_cli_grava_no_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YBY_VAULT_PATH", str(tmp_path))
    result = CliRunner().invoke(cli, ["note", "ideia", "memória local"])
    assert result.exit_code == 0
    assert (tmp_path / "ideia.md").read_text(encoding="utf-8").startswith("memória")


def test_vault_em_arquivo_comum_levanta_vault_error(tmp_path: Path) -> None:
    arquivo = tmp_path / "nao-e-pasta"
    arquivo.write_text("x", encoding="utf-8")

    with pytest.raises(VaultError, match="caminho do vault inválido"):
        Vault(arquivo)
    with pytest.raises(VaultError, match="caminho do vault inválido"):
        Vault(arquivo / "filho")


@pytest.mark.parametrize("subcaminho", ["", "filho"])
def test_cli_recall_com_vault_em_arquivo_comum_falha_com_erro_controlado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, subcaminho: str
) -> None:
    arquivo = tmp_path / "nao-e-pasta"
    arquivo.write_text("x", encoding="utf-8")
    monkeypatch.setattr("src.main.load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("YBY_VAULT_PATH", str(arquivo / subcaminho) if subcaminho else str(arquivo))

    result = CliRunner().invoke(cli, ["recall", "bolo"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "caminho do vault inválido" in result.stderr
    assert str(arquivo) in result.stderr
    assert "Traceback" not in result.output
    assert result.stdout == ""
    assert arquivo.read_text(encoding="utf-8") == "x"


def test_cli_recall_com_vault_valido_segue_igual(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("src.main.load_dotenv", lambda *args, **kwargs: False)
    Vault(tmp_path / "vault").write_note("receitas/bolo", "bolo de cenoura")
    monkeypatch.setenv("YBY_VAULT_PATH", str(tmp_path / "vault"))

    achou = CliRunner().invoke(cli, ["recall", "bolo de cenoura"])
    assert achou.exit_code == 0
    assert "receitas/bolo.md" in achou.output

    monkeypatch.setenv("YBY_VAULT_PATH", str(tmp_path / "novo"))
    vazio = CliRunner().invoke(cli, ["recall", "bolo"])
    assert vazio.exit_code == 0
    assert vazio.output.strip() == "Nenhuma nota."
    assert (tmp_path / "novo").is_dir()


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
