"""Testes do briefing declarativo de skills."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.safety.policy import SKILL_ACTIONS, is_allowed_skill_action
from src.skills.briefing import ActionBriefing


def _briefing(**overrides):
    values = {
        "skill_name": "backup-automation",
        "request": "Fazer backup dos PDFs",
        "action": "copy_files_to_backup_dir",
        "inputs": (
            ("source_dir", "/home/usuario/Documents"),
            ("destination_dir", "/home/usuario/Backups/yby/2026-11-22"),
            ("file_pattern", "*.pdf"),
            ("overwrite", "false"),
        ),
        "effects": (
            "Criar o diretório de destino se ele não existir",
            "Copiar os arquivos correspondentes sem sobrescrever",
            "Não remover arquivos de origem",
        ),
        "risks": (
            "Nenhum acesso à rede",
            "Nenhum script será executado",
            "Nenhum arquivo será sobrescrito",
        ),
    }
    values.update(overrides)
    return ActionBriefing(**values)


def test_valid_briefing_has_pending_status_and_hash():
    briefing = _briefing()

    assert briefing.status == "pending"
    assert briefing.briefing_hash
    assert briefing.briefing_id == f"sha256:{briefing.briefing_hash}"
    assert briefing.action in SKILL_ACTIONS


def test_hash_is_deterministic():
    first = _briefing()
    second = _briefing()

    assert first.briefing_hash == second.briefing_hash
    assert first.canonical_json() == second.canonical_json()


def test_hash_changes_when_approved_content_changes():
    original = _briefing()
    changed = _briefing(request="Fazer backup dos PDFs importantes")

    assert original.briefing_hash != changed.briefing_hash


def test_hash_ignores_input_order():
    original = _briefing()
    reordered = _briefing(
        inputs=(
            ("file_pattern", "*.pdf"),
            ("overwrite", "false"),
            ("source_dir", "/home/usuario/Documents"),
            ("destination_dir", "/home/usuario/Backups/yby/2026-11-22"),
        )
    )

    assert original.briefing_hash == reordered.briefing_hash


def test_briefing_is_immutable():
    briefing = _briefing()

    with pytest.raises(FrozenInstanceError):
        briefing.request = "novo pedido"


def test_rejects_action_outside_allowlist():
    with pytest.raises(ValueError, match="Ação não permitida"):
        _briefing(action="run_script")


def test_rejects_empty_required_text():
    with pytest.raises(ValueError, match="skill_name"):
        _briefing(skill_name="  ")


def test_rejects_empty_inputs():
    with pytest.raises(ValueError, match="inputs"):
        _briefing(inputs=())


def test_rejects_duplicate_input_keys():
    with pytest.raises(ValueError, match="Entrada duplicada"):
        _briefing(
            inputs=(
                ("source_dir", "/home/usuario/Documents"),
                ("source_dir", "/home/usuario/Documents"),
            )
        )


def test_rejects_malformed_input():
    with pytest.raises(ValueError, match="par imutável"):
        _briefing(inputs=(("source_dir",),))


def test_rejects_empty_effects():
    with pytest.raises(ValueError, match="effects"):
        _briefing(effects=())


def test_rejects_empty_risks():
    with pytest.raises(ValueError, match="risks"):
        _briefing(risks=())


def test_canonical_json_contains_schema_version():
    briefing = _briefing()

    assert '"schema_version":1' in briefing.canonical_json()
    assert '"action":"copy_files_to_backup_dir"' in briefing.canonical_json()


def test_skill_actions_allowlist_contains_backup_action():
    assert "copy_files_to_backup_dir" in SKILL_ACTIONS


def test_is_allowed_skill_action_accepts_known_action():
    assert is_allowed_skill_action("copy_files_to_backup_dir") is True


def test_is_allowed_skill_action_refuses_unknown_action():
    assert is_allowed_skill_action("run_script") is False
    assert is_allowed_skill_action("install") is False
    assert is_allowed_skill_action("network") is False
    assert is_allowed_skill_action("delete") is False
