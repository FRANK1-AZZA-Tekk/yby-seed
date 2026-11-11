"""Executa um comando de shell só após a porta de segurança permitir.

`src/safety` decide e confirma. Este módulo só chama o subprocesso quando a
decisão é `run`, ou `ask` com sim. `refuse` nunca chega ao subprocesso.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from src.safety.policy import (
    Decision,
    Policy,
    confirm,
    decide,
    default_policy_path,
    load_policy,
)

DEFAULT_TIMEOUT = 30.0

Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class RunResult:
    """Resultado da tentativa de execução."""

    decision: Decision
    approved: bool
    executed: bool
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False


def run_command(
    command: str,
    *,
    policy: Policy | None = None,
    project_root: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    input_fn: Callable[[], str] = input,
    output_fn: Callable[[str], None] = print,
    runner: Runner | None = None,
    cwd: Path | str | None = None,
) -> RunResult:
    """Decide com a safety, confirma se preciso, e só então executa."""

    root = Path(project_root) if project_root is not None else default_policy_path().parents[1]
    active_policy = policy if policy is not None else load_policy(default_policy_path())
    decision = decide(command, policy=active_policy, project_root=root)

    if decision.action == "refuse":
        output_fn(f"refuse: {decision.reason}")
        return RunResult(
            decision=decision,
            approved=False,
            executed=False,
            exit_code=None,
            stdout="",
            stderr="",
        )

    approved = confirm(
        command,
        decision,
        input_fn=input_fn,
        output_fn=output_fn,
    )
    if not approved:
        return RunResult(
            decision=decision,
            approved=False,
            executed=False,
            exit_code=None,
            stdout="",
            stderr="",
        )

    argv = _argv(command)
    workdir = Path(cwd) if cwd is not None else root
    execute = runner or _default_runner

    try:
        completed = execute(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(workdir),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _as_text(exc.stdout)
        stderr = _as_text(exc.stderr)
        if not stderr:
            stderr = f"timeout após {timeout:g}s"
        return RunResult(
            decision=decision,
            approved=True,
            executed=True,
            exit_code=None,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
        )

    return RunResult(
        decision=decision,
        approved=True,
        executed=True,
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def _argv(command: str) -> Sequence[str]:
    return shlex.split(command.strip(), posix=True)


def _default_runner(
    argv: Sequence[str],
    *,
    capture_output: bool,
    text: bool,
    timeout: float,
    cwd: str,
    check: bool,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        capture_output=capture_output,
        text=text,
        timeout=timeout,
        cwd=cwd,
        check=check,
        shell=False,
    )


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
