"""Autorização Etapa 4: classificação + sem subprocess nos bloqueios."""

from __future__ import annotations

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
examples

[refuse]
rm -rf /
git push --force
git reset --hard
git clean -fd
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


def _boom_subprocess(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    hits = {"run": 0, "popen": 0}

    def boom_run(*_a, **_k):
        hits["run"] += 1
        raise AssertionError("subprocess.run não deve ser chamado")

    def boom_popen(*_a, **_k):
        hits["popen"] += 1
        raise AssertionError("subprocess.Popen não deve ser chamado")

    monkeypatch.setattr(subprocess, "run", boom_run)
    monkeypatch.setattr(subprocess, "Popen", boom_popen)
    return hits


def test_bloqueados_nao_iniciam_processo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _policy(tmp_path)
    hits = _boom_subprocess(monkeypatch)
    runner = _fake_runner()
    blocked = [
        "git config audit.example changed",
        "git push origin main",
        "git --no-pager reset --hard",
        "git -c alias.x=!id x",
        f"{tmp_path / 'evil' / 'git'} status",
        "date --set=2030-01-01",
    ]
    (tmp_path / "evil").mkdir()
    (tmp_path / "evil" / "git").write_text("#!/bin/sh\n", encoding="utf-8")

    for command in blocked:
        result = run_command(
            command,
            policy=policy,
            project_root=tmp_path,
            input_fn=lambda: "n",
            output_fn=lambda _line: None,
            runner=runner,
        )
        assert result.executed is False, command
        assert result.decision.action in {"ask", "refuse"}, (
            command,
            result.decision.action,
        )

    assert runner.calls == []
    assert hits["run"] == 0
    assert hits["popen"] == 0


def test_script_por_pasta_nao_auto_executa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _policy(tmp_path)
    _boom_subprocess(monkeypatch)
    script = tmp_path / "scripts" / "powerful.py"
    script.parent.mkdir()
    script.write_text("print('x')\n", encoding="utf-8")
    runner = _fake_runner()

    assert decide(f"python {script}", policy=policy, project_root=tmp_path).action == "ask"
    result = run_command(
        f"python {script}",
        policy=policy,
        project_root=tmp_path,
        input_fn=lambda: "n",
        output_fn=lambda _line: None,
        runner=runner,
    )
    assert result.executed is False
    assert runner.calls == []


def test_leitura_autorizada_argv_bate(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    runner = _fake_runner()
    result = run_command(
        "ls -la",
        policy=policy,
        project_root=tmp_path,
        input_fn=lambda: (_ for _ in ()).throw(AssertionError("não pergunta")),
        output_fn=lambda _line: None,
        runner=runner,
    )
    assert result.executed is True
    assert runner.calls[0]["argv"] == ["ls", "-la"]


def test_ask_eof_nao_executa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _policy(tmp_path)
    _boom_subprocess(monkeypatch)
    runner = _fake_runner()

    def _eof() -> str:
        raise EOFError

    result = run_command(
        "rm arquivo.txt",
        policy=policy,
        project_root=tmp_path,
        input_fn=_eof,
        output_fn=lambda _line: None,
        runner=runner,
    )
    assert result.decision.action == "ask"
    assert result.approved is False
    assert result.executed is False
    assert runner.calls == []


def test_symlink_script_fora_pede_confirmacao(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    outside = tmp_path.parent / f"fora-{tmp_path.name}.py"
    outside.write_text("print(1)\n", encoding="utf-8")
    link_dir = tmp_path / "scripts"
    link_dir.mkdir()
    link = link_dir / "link.py"
    link.symlink_to(outside)
    assert decide(f"python {link}", policy=policy, project_root=tmp_path).action == "ask"
