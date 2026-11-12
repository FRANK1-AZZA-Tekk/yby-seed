"""MVP exocórtex: skill → dry-run → confirmação → ledger."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.actions.runner import RunResult
from src.orchestration.exocortex import propose_shell_command, run_exocortex
from src.orchestration.ledger import read_recent_events
from src.safety.policy import Decision
from src.skills.skill_manager import SkillManager


@pytest.fixture
def repo_skills() -> Path:
    return Path(__file__).resolve().parents[1] / "skills"


def test_find_file_operations_skill(repo_skills: Path) -> None:
    mgr = SkillManager(skills_dir=str(repo_skills))
    mgr.discover_skills()
    skill = mgr.find_best_skill("listar arquivos da pasta atual")
    assert skill is not None
    assert skill.metadata.name == "file-operations"


def test_propose_ls_for_listar() -> None:
    mgr = SkillManager(skills_dir=str(Path(__file__).resolve().parents[1] / "skills"))
    mgr.discover_skills()
    skill = mgr.find_best_skill("listar arquivos")
    assert propose_shell_command("listar arquivos", skill) == "ls"


def test_exocortex_flow_auto_yes(
    tmp_path: Path, repo_skills: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = tmp_path / "ledger.jsonl"

    def _append(event: dict, path=None):
        from src.orchestration import ledger as ledger_mod

        return ledger_mod.append_ledger_event(event, path=ledger)

    monkeypatch.setattr("src.orchestration.exocortex.append_ledger_event", _append)

    def fake_run(command: str, **kwargs) -> RunResult:
        return RunResult(
            decision=Decision("run", "test"),
            approved=True,
            executed=True,
            exit_code=0,
            stdout="file.txt\n",
            stderr="",
        )

    monkeypatch.setattr("src.orchestration.exocortex.run_command", fake_run)

    out = run_exocortex(
        "listar arquivos do projeto",
        auto_yes=True,
        skills_dir=repo_skills,
        project_root=Path(__file__).resolve().parents[1],
        input_fn=lambda: "s",
        output_fn=lambda _m: None,
        record_vault_fn=None,
    )
    assert out.mode == "skill"
    assert out.executed is True
    assert out.skill_name == "file-operations"
    events = read_recent_events(path=ledger, limit=5)
    assert events
    assert events[-1]["status"] == "executed"


def test_exocortex_cancelled_on_no(
    tmp_path: Path, repo_skills: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = tmp_path / "ledger.jsonl"

    def _append(event: dict, path=None):
        from src.orchestration import ledger as ledger_mod

        return ledger_mod.append_ledger_event(event, path=ledger)

    monkeypatch.setattr("src.orchestration.exocortex.append_ledger_event", _append)
    monkeypatch.setattr("src.orchestration.exocortex.run_command", MagicMock())

    out = run_exocortex(
        "listar arquivos da pasta",
        auto_yes=False,
        skills_dir=repo_skills,
        project_root=Path(__file__).resolve().parents[1],
        input_fn=lambda: "n",
        output_fn=lambda _m: None,
    )
    assert out.approved is False
    assert out.executed is False
    events = read_recent_events(path=ledger)
    assert events[-1]["status"] == "cancelled"
