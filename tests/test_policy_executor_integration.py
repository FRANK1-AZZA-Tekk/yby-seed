"""Integração policy ↔ executor: mesmo argv/cwd; mocks + ls inofensivo."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from src.actions.runner import run_command
from src.safety.policy import decide, load_policy

ALLOWLIST = """
[read]
ls
cat
date

[git]
git

[scripts]
scripts

[refuse]
rm -rf /
git push --force
git reset --hard
"""


def _policy(tmp_path: Path):
    path = tmp_path / "allowlist.txt"
    path.write_text(ALLOWLIST, encoding="utf-8")
    return load_policy(path)


def _fake_runner():
    calls: list[dict[str, object]] = []

    def runner(argv, **kwargs):
        calls.append({"argv": list(argv), **kwargs})
        return subprocess.CompletedProcess(
            args=list(argv),
            returncode=0,
            stdout="ok\n",
            stderr="",
        )

    runner.calls = calls  # type: ignore[attr-defined]
    return runner


def _boom_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom_run(*_a, **_k):
        raise AssertionError("subprocess.run não deve ser chamado")

    def boom_popen(*_a, **_k):
        raise AssertionError("subprocess.Popen não deve ser chamado")

    monkeypatch.setattr(subprocess, "run", boom_run)
    monkeypatch.setattr(subprocess, "Popen", boom_popen)


def test_ask_recusa_e_eof_nao_iniciam_processo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = _policy(tmp_path)
    _boom_subprocess(monkeypatch)
    runner = _fake_runner()

    denied = run_command(
        "rm arquivo.txt",
        policy=policy,
        project_root=tmp_path,
        input_fn=lambda: "n",
        output_fn=lambda _line: None,
        runner=runner,
    )
    assert denied.decision.action == "ask"
    assert denied.executed is False

    refused = run_command(
        "rm -rf /",
        policy=policy,
        project_root=tmp_path,
        input_fn=lambda: "s",
        output_fn=lambda _line: None,
        runner=runner,
    )
    assert refused.decision.action == "refuse"
    assert refused.executed is False

    def _eof() -> str:
        raise EOFError

    eof = run_command(
        "rm arquivo.txt",
        policy=policy,
        project_root=tmp_path,
        input_fn=_eof,
        output_fn=lambda _line: None,
        runner=runner,
    )
    assert eof.approved is False
    assert eof.executed is False
    assert runner.calls == []


def test_run_usa_argv_e_workdir_da_decisao(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    runner = _fake_runner()
    work = tmp_path / "work"
    work.mkdir()

    result = run_command(
        "ls -la",
        policy=policy,
        project_root=tmp_path,
        cwd=work,
        input_fn=lambda: (_ for _ in ()).throw(AssertionError("não pergunta")),
        output_fn=lambda _line: None,
        runner=runner,
    )

    assert result.decision.action == "run"
    assert result.decision.argv == ("ls", "-la")
    assert result.decision.workdir == str(work.resolve())
    assert result.executed is True
    assert runner.calls[0]["argv"] == list(result.decision.argv)
    assert runner.calls[0]["cwd"] == result.decision.workdir


def test_decide_e_run_compartilham_workdir_explicito(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    work = tmp_path / "cwd-a"
    work.mkdir()
    decision = decide(
        "ls",
        policy=policy,
        project_root=tmp_path,
        workdir=work,
    )
    assert decision.workdir == str(work.resolve())
    assert decision.argv == ("ls",)

    runner = _fake_runner()
    result = run_command(
        "ls",
        policy=policy,
        project_root=tmp_path,
        cwd=work,
        input_fn=lambda: "n",
        output_fn=lambda _line: None,
        runner=runner,
    )
    assert result.decision.workdir == decision.workdir
    assert result.decision.argv == decision.argv
    assert runner.calls[0]["cwd"] == decision.workdir


def test_parse_invalido_com_sim_nao_executa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = _policy(tmp_path)
    _boom_subprocess(monkeypatch)
    runner = _fake_runner()
    result = run_command(
        "echo 'unterminated",
        policy=policy,
        project_root=tmp_path,
        input_fn=lambda: "s",
        output_fn=lambda _line: None,
        runner=runner,
    )
    assert result.decision.action == "ask"
    assert result.decision.argv == ()
    assert result.approved is True
    assert result.executed is False
    assert runner.calls == []


@pytest.mark.skipif(shutil.which("ls") is None, reason="ls não está no PATH")
def test_ls_inofensivo_real_em_tmp(tmp_path: Path) -> None:
    """Sem mock: ls allowlisted no diretório temporário."""
    policy = _policy(tmp_path)
    marker = tmp_path / "hello.txt"
    marker.write_text("hi\n", encoding="utf-8")

    result = run_command(
        "ls",
        policy=policy,
        project_root=tmp_path,
        cwd=tmp_path,
        input_fn=lambda: (_ for _ in ()).throw(AssertionError("não pergunta")),
        output_fn=lambda _line: None,
    )

    assert result.decision.action == "run"
    assert result.decision.argv == ("ls",)
    assert result.decision.workdir == str(tmp_path.resolve())
    assert result.executed is True
    assert result.exit_code == 0
    assert "hello.txt" in result.stdout
