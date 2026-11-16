"""Lote 20: preferências no vault com consentimento."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from src.main import cli
from src.memory.prefs import PrefsError, get_pref, list_prefs, prefs_path, set_pref
from src.memory.vault import Vault


def test_locale_sem_consent(tmp_path: Path) -> None:
    vault = Vault(tmp_path)
    record = set_pref(vault, "locale", "pt-BR")
    assert record.value == "pt-BR"
    assert record.consent_at is None
    assert get_pref(vault, "locale").value == "pt-BR"
    assert prefs_path(vault).is_file()


def test_share_notes_exige_consent(tmp_path: Path) -> None:
    vault = Vault(tmp_path)
    with pytest.raises(PrefsError, match="consentimento"):
        set_pref(vault, "share_notes_with_cloud", "1", consent=False)
    record = set_pref(vault, "share_notes_with_cloud", "true", consent=True)
    assert record.value == "1"
    assert record.consent_at is not None
    data = json.loads(prefs_path(vault).read_text(encoding="utf-8"))
    assert data["preferences"]["share_notes_with_cloud"]["consent_at"]


def test_valor_com_segredo_bloqueado(tmp_path: Path) -> None:
    vault = Vault(tmp_path)
    with pytest.raises(PrefsError, match="segredo"):
        set_pref(
            vault,
            "locale",
            "sk-or-v1-abcdefghijklmnopqrstuvwxyz012345",
        )


def test_chave_desconhecida(tmp_path: Path) -> None:
    vault = Vault(tmp_path)
    with pytest.raises(PrefsError, match="desconhecida"):
        set_pref(vault, "telemetry_phone_home", "1", consent=True)


def test_cli_prefs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YBY_VAULT_PATH", str(tmp_path))
    runner = CliRunner()

    denied = runner.invoke(cli, ["prefs", "set", "remember_failures", "1"])
    assert denied.exit_code == 1
    assert "consentimento" in denied.output.lower()

    ok = runner.invoke(
        cli, ["prefs", "set", "remember_failures", "1", "--consent"]
    )
    assert ok.exit_code == 0, ok.output
    assert "remember_failures=1" in ok.output
    assert "consent_at=" in ok.output

    style = runner.invoke(cli, ["prefs", "set", "reply_style", "teach"])
    assert style.exit_code == 0, style.output

    listed = runner.invoke(cli, ["prefs", "list"])
    assert listed.exit_code == 0
    assert "reply_style=teach" in listed.output
    assert "remember_failures=1" in listed.output

    got = runner.invoke(cli, ["prefs", "get", "reply_style"])
    assert got.exit_code == 0
    assert "teach" in got.output

    assert len(list_prefs(Vault(tmp_path))) == 2
