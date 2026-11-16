"""Etapa 3 — matriz de riscos da política (classificação + mocks; sem efeitos reais).

Não altera produção. Documenta hipóteses: alguns asserts codificam o comportamento
seguro esperado (falhas possíveis se a produção ainda for permissiva ou divergir).
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

import pytest

from src.actions.runner import run_command
from src.safety.policy import Decision, confirm, decide, load_policy

ALLOWLIST = """
[read]
ls
cat
df
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


def _run_denied(tmp_path: Path, command: str, monkeypatch: pytest.MonkeyPatch, answer: str = "n"):
    policy = _policy(tmp_path)
    hits = _boom_subprocess(monkeypatch)
    runner = _fake_runner()
    result = run_command(
        command,
        policy=policy,
        project_root=tmp_path,
        input_fn=lambda: answer,
        output_fn=lambda _line: None,
        runner=runner,
    )
    assert result.executed is False
    assert runner.calls == []
    assert hits["run"] == 0
    assert hits["popen"] == 0
    return result


# --- git / refuse -----------------------------------------------------------


def test_git_config_ask_sem_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _policy(tmp_path)
    assert decide("git config audit.example changed", policy=policy, project_root=tmp_path).action == "ask"
    result = _run_denied(tmp_path, "git config audit.example changed", monkeypatch)
    assert result.decision.action == "ask"


def test_git_push_ask_sem_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _policy(tmp_path)
    assert decide("git push origin main", policy=policy, project_root=tmp_path).action == "ask"
    result = _run_denied(tmp_path, "git push origin main", monkeypatch)
    assert result.decision.action == "ask"


def test_git_reset_hard_direto_refuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _policy(tmp_path)
    assert decide("git reset --hard", policy=policy, project_root=tmp_path).action == "refuse"
    result = _run_denied(tmp_path, "git reset --hard", monkeypatch)
    assert result.decision.action == "refuse"


def test_git_reset_hard_com_no_pager_nao_e_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contrato seguro: flags globais não bypassam refuse estrutural."""
    policy = _policy(tmp_path)
    action = decide("git --no-pager reset --hard", policy=policy, project_root=tmp_path).action
    assert action == "refuse"
    result = _run_denied(tmp_path, "git --no-pager reset --hard", monkeypatch)
    assert result.decision.action == "refuse"
    assert result.executed is False


def test_git_alias_shell_refuse_sem_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = _policy(tmp_path)
    assert decide("git -c alias.x=!id x", policy=policy, project_root=tmp_path).action == "refuse"
    result = _run_denied(tmp_path, "git -c alias.x=!id x", monkeypatch)
    assert result.decision.action == "refuse"


# --- riscos abertos (asserts seguros) ---------------------------------------


def test_fake_git_path_nao_e_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Assert seguro: path falso chamado git não pode ser run automático."""
    policy = _policy(tmp_path)
    fake = tmp_path / "bin" / "git"
    fake.parent.mkdir()
    fake.write_text("#!/bin/sh\necho pwn\n", encoding="utf-8")
    command = f"{fake} status"
    action = decide(command, policy=policy, project_root=tmp_path).action
    assert action in {"ask", "refuse"}
    result = _run_denied(tmp_path, command, monkeypatch)
    assert result.executed is False


def test_date_set_nao_e_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Assert seguro: date --set não pode ser run automático."""
    policy = _policy(tmp_path)
    command = "date --set=2030-01-01"
    assert decide(command, policy=policy, project_root=tmp_path).action != "run"
    result = _run_denied(tmp_path, command, monkeypatch)
    assert result.executed is False


def test_script_por_pasta_pede_confirmacao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pasta scripts/examples não confere auto-exec; pede confirmação."""
    policy = _policy(tmp_path)
    script = tmp_path / "scripts" / "powerful.py"
    script.parent.mkdir()
    script.write_text("print('powerful')\n", encoding="utf-8")
    example = tmp_path / "examples" / "x.sh"
    example.parent.mkdir()
    example.write_text("#!/bin/sh\necho x\n", encoding="utf-8")

    assert decide(f"python {script}", policy=policy, project_root=tmp_path).action == "ask"
    assert decide(f"bash {example}", policy=policy, project_root=tmp_path).action == "ask"
    result = _run_denied(tmp_path, f"python {script}", monkeypatch)
    assert result.executed is False


# --- borda / execução -------------------------------------------------------


def test_leitura_permitida_e_argv(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    runner = _fake_runner(stdout="arquivo\n")
    assert decide("ls", policy=policy, project_root=tmp_path).action == "run"
    assert decide("cat README.md", policy=policy, project_root=tmp_path).action == "run"

    result = run_command(
        "ls -la",
        policy=policy,
        project_root=tmp_path,
        input_fn=lambda: (_ for _ in ()).throw(AssertionError("não deve perguntar")),
        output_fn=lambda _line: None,
        runner=runner,
    )
    assert result.executed is True
    assert runner.calls[0]["argv"] == ["ls", "-la"]


def test_comando_vazio_refuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _policy(tmp_path)
    assert decide("", policy=policy, project_root=tmp_path).action == "refuse"
    result = _run_denied(tmp_path, "   ", monkeypatch)
    assert result.decision.action == "refuse"


def test_comando_desconhecido_ask(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _policy(tmp_path)
    assert decide("foobar --wat", policy=policy, project_root=tmp_path).action == "ask"
    result = _run_denied(tmp_path, "foobar --wat", monkeypatch)
    assert result.decision.action == "ask"


def test_argumentos_invalidos_shlex_ask(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    assert decide("echo 'unterminated", policy=policy, project_root=tmp_path).action == "ask"


def test_symlink_fora_da_politica_ask(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _policy(tmp_path)
    outside = tmp_path.parent / f"fora-risk-{tmp_path.name}.py"
    outside.write_text("print(1)\n", encoding="utf-8")
    link_dir = tmp_path / "scripts"
    link_dir.mkdir()
    link = link_dir / "link.py"
    link.symlink_to(outside)

    command = f"python {link}"
    assert decide(command, policy=policy, project_root=tmp_path).action == "ask"
    result = _run_denied(tmp_path, command, monkeypatch)
    assert result.executed is False


def test_aprovacao_e_recusa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _policy(tmp_path)
    decision = decide("rm arquivo.txt", policy=policy, project_root=tmp_path)
    assert decision.action == "ask"

    said: list[str] = []
    assert confirm("rm arquivo.txt", decision, input_fn=lambda: "s", output_fn=said.append) is True
    assert confirm("rm arquivo.txt", decision, input_fn=lambda: "n", output_fn=said.append) is False

    runner_yes = _fake_runner()
    yes = run_command(
        "rm arquivo.txt",
        policy=policy,
        project_root=tmp_path,
        input_fn=lambda: "s",
        output_fn=lambda _line: None,
        runner=runner_yes,
    )
    assert yes.executed is True
    assert runner_yes.calls[0]["argv"] == shlex.split("rm arquivo.txt")

    _boom_subprocess(monkeypatch)
    runner_no = _fake_runner()
    no = run_command(
        "rm arquivo.txt",
        policy=policy,
        project_root=tmp_path,
        input_fn=lambda: "n",
        output_fn=lambda _line: None,
        runner=runner_no,
    )
    assert no.executed is False
    assert runner_no.calls == []


def test_eof_sem_tty_nao_executa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem interação (EOF), ask não autoriza execução."""
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


def test_auth_exec_correspondencia_apos_sim(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    command = "rm arquivo.txt"
    runner = _fake_runner()
    result = run_command(
        command,
        policy=policy,
        project_root=tmp_path,
        input_fn=lambda: "s",
        output_fn=lambda _line: None,
        runner=runner,
    )
    assert result.decision.action == "ask"
    assert result.executed is True
    assert runner.calls[0]["argv"] == shlex.split(command)


def test_decision_run_continua_leitura(tmp_path: Path) -> None:
    """Sanidade: Decision run ainda aprova sem input."""
    decision = Decision("run", "comando somente leitura: ls")
    assert confirm("ls", decision, input_fn=lambda: "n", output_fn=lambda _line: None) is True
