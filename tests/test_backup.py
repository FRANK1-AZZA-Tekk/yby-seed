"""Backup local do vault + logs redigidos (lote 23)."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from src.backup.local import (
    BackupError,
    create_backup,
    list_backups,
    restore_backup,
)
from src.main import cli
from src.memory.vault import Vault


def test_create_restore_roundtrip(tmp_path: Path) -> None:
    vault = Vault(tmp_path / "vault")
    vault.write_note("diario", "nota segura do hub\n")
    log_path = tmp_path / "cloud_usage.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "timestamp": 1,
                "provider": "openrouter",
                "model": "m",
                "purpose": "t",
                "input_tokens_estimate": 1,
                "output_tokens_estimate": 1,
                "result": "cloud_completed",
                "detail": "chave sk-or-v1-abcdefghijklmnopqrstuvwxyz012345",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    backup_dir = tmp_path / "backups"
    info = create_backup(
        vault_path=vault.root,
        backup_dir=backup_dir,
        log_paths=[log_path],
        keep=7,
        now=1_700_000_000.0,
    )
    assert info.path.is_file()
    assert info.path.name.startswith("yby-backup-")

    with tarfile.open(info.path, "r:gz") as tar:
        names = set(tar.getnames())
        assert "manifest.json" in names
        assert any(name.startswith("vault/") for name in names)
        member = tar.getmember("logs/cloud_usage.jsonl")
        extracted = tar.extractfile(member)
        assert extracted is not None
        body = extracted.read().decode("utf-8")
    assert "sk-or-v1-abcdefghijklmnopqrstuvwxyz012345" not in body
    assert "[API_KEY_REDACTED]" in body

    target = tmp_path / "restored"
    restore_backup(info.path, target)
    assert (target / "diario.md").read_text(encoding="utf-8").startswith("nota segura")


def test_restore_recusa_alvo_nao_vazio(tmp_path: Path) -> None:
    vault = Vault(tmp_path / "vault")
    vault.write_note("a", "um\n")
    backup_dir = tmp_path / "backups"
    info = create_backup(
        vault_path=vault.root,
        backup_dir=backup_dir,
        log_paths=[],
        keep=3,
    )
    target = tmp_path / "out"
    target.mkdir()
    (target / "ja_existe.md").write_text("x\n", encoding="utf-8")
    with pytest.raises(BackupError, match="não vazio"):
        restore_backup(info.path, target)
    restore_backup(info.path, target, force=True)
    assert (target / "a.md").is_file()


def test_retenção_mantem_n_mais_recentes(tmp_path: Path) -> None:
    vault = Vault(tmp_path / "vault")
    vault.write_note("n", "x\n")
    backup_dir = tmp_path / "backups"
    for i in range(5):
        create_backup(
            vault_path=vault.root,
            backup_dir=backup_dir,
            log_paths=[],
            keep=3,
            now=1_700_000_000.0 + i,
        )
    items = list_backups(backup_dir)
    assert len(items) == 3
    assert items[0].stamp > items[-1].stamp


def test_cli_backup_create_list_restore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault_path = tmp_path / "vault"
    Vault(vault_path).write_note("cli", "via cli\n")
    backup_dir = tmp_path / "backups"
    restore_dir = tmp_path / "restore"
    monkeypatch.setenv("YBY_VAULT_PATH", str(vault_path))
    monkeypatch.setenv("YBY_BACKUP_DIR", str(backup_dir))
    monkeypatch.setenv("YBY_CLOUD_LOG_PATH", str(tmp_path / "missing.jsonl"))

    runner = CliRunner()
    created = runner.invoke(cli, ["backup", "create", "--keep", "5"])
    assert created.exit_code == 0, created.output
    assert "yby-backup-" in created.output

    listed = runner.invoke(cli, ["backup", "list"])
    assert listed.exit_code == 0
    assert "yby-backup-" in listed.output

    archive = next(backup_dir.glob("yby-backup-*.tar.gz"))
    restored = runner.invoke(cli, ["backup", "restore", str(archive), str(restore_dir)])
    assert restored.exit_code == 0, restored.output
    assert (restore_dir / "cli.md").read_text(encoding="utf-8").startswith("via cli")
