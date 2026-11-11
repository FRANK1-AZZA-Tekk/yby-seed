"""Camada Actions: executa só depois da safety. Sem comandos reais destrutivos."""

from __future__ import annotations

import subprocess
from pathlib import Path

from click.testing import CliRunner

from src.actions.runner import run_command
from src.main import cli
from src.safety.policy import load_policy

ALLOWLIST = """
[read]
ls
cat
df

[git]
git

[scripts]
scripts

[refuse]
rm -rf /
git push --force
"""


def _policy(tmp_path: Path):
    path = tmp_path / "allowlist.txt"
    path.write_text(ALLOWLIST, encoding="utf-8")
    return load_policy(path)


def _fake_runner(stdout: str = "ok\n", stderr: str = "", returncode: int = 0):
    calls: list[dict[str, object]] = []

    def runner(argv, **kwargs):
        calls.append({"argv": list(argv), **kwargs})
        return subprocess.CompletedProcess(
            args=list(argv),
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    runner.calls = calls  # type: ignore[attr-defined]
    return runner


def test_allowlist_executa_sem_perguntar(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    runner = _fake_runner(stdout="arquivo\n")
    said: list[str] = []

    result = run_command(
        "ls -la",
        policy=policy,
        project_root=tmp_path,
        input_fn=lambda: (_ for _ in ()).throw(AssertionError("não deve perguntar")),
        output_fn=said.append,
        runner=runner,
    )

    assert result.approved is True
    assert result.executed is True
    assert result.exit_code == 0
    assert result.stdout == "arquivo\n"
    assert runner.calls[0]["argv"] == ["ls", "-la"]
    assert runner.calls[0]["timeout"] == 30.0


def test_ask_com_sim_executa(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    runner = _fake_runner(stdout="", returncode=0)
    answers = iter(["s"])
    said: list[str] = []

    result = run_command(
        "rm arquivo.txt",
        policy=policy,
        project_root=tmp_path,
        input_fn=lambda: next(answers),
        output_fn=said.append,
        runner=runner,
    )

    assert result.decision.action == "ask"
    assert result.approved is True
    assert result.executed is True
    assert runner.calls[0]["argv"] == ["rm", "arquivo.txt"]
    assert any("s/n" in line for line in said)


def test_ask_com_nao_nao_executa(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    runner = _fake_runner()
    said: list[str] = []

    result = run_command(
        "rm arquivo.txt",
        policy=policy,
        project_root=tmp_path,
        input_fn=lambda: "n",
        output_fn=said.append,
        runner=runner,
    )

    assert result.approved is False
    assert result.executed is False
    assert result.exit_code is None
    assert runner.calls == []


def test_refuse_nunca_executa(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    runner = _fake_runner()
    asked = {"sim": False}

    def _boom() -> str:
        asked["sim"] = True
        return "s"

    result = run_command(
        "rm -rf /",
        policy=policy,
        project_root=tmp_path,
        input_fn=_boom,
        output_fn=lambda _line: None,
        runner=runner,
    )

    assert result.decision.action == "refuse"
    assert result.approved is False
    assert result.executed is False
    assert runner.calls == []
    assert asked["sim"] is False


def test_timeout_nao_trava(tmp_path: Path) -> None:
    policy = _policy(tmp_path)

    def runner(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=list(argv), timeout=kwargs["timeout"])

    result = run_command(
        "ls",
        policy=policy,
        project_root=tmp_path,
        timeout=0.1,
        input_fn=lambda: "n",
        output_fn=lambda _line: None,
        runner=runner,
    )

    assert result.approved is True
    assert result.executed is True
    assert result.timed_out is True
    assert result.exit_code is None
    assert "timeout" in result.stderr


def test_cli_run_usa_a_camada(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_run_command(command: str, **kwargs):
        calls.append({"command": command, **kwargs})
        from src.actions.runner import RunResult
        from src.safety.policy import Decision

        return RunResult(
            decision=Decision("run", "comando somente leitura: ls"),
            approved=True,
            executed=True,
            exit_code=0,
            stdout="ok\n",
            stderr="",
        )

    monkeypatch.setattr("src.main.run_command", fake_run_command)
    result = CliRunner().invoke(cli, ["run", "ls", "-la"])

    assert result.exit_code == 0
    assert "ok" in result.output
    assert calls[0]["command"] == "ls -la"


def test_cli_run_recusa_termina_com_erro(monkeypatch) -> None:
    from src.actions.runner import RunResult
    from src.safety.policy import Decision

    def fake_run_command(command: str, **kwargs):
        return RunResult(
            decision=Decision("refuse", "padrão destrutivo: rm -rf /"),
            approved=False,
            executed=False,
            exit_code=None,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr("src.main.run_command", fake_run_command)
    result = CliRunner().invoke(cli, ["run", "rm", "-rf", "/"])
    assert result.exit_code == 1
