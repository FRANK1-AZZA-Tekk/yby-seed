"""Executa um comando de shell só após a porta de segurança permitir.

`src/safety` decide e confirma. Este módulo só chama o subprocesso quando a
decisão é `run`, ou `ask` com sim. `refuse` nunca chega ao subprocesso.
O executor usa exatamente `decision.argv` e `decision.workdir` autorizados.
Limites (lote 24): timeout com teto, truncagem de saída, bloqueio sob scaffold.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from src.actions.limits import (
    DEFAULT_TIMEOUT,
    RunnerLimitError,
    assert_not_generated_execution,
    normalize_timeout,
    output_max_bytes_from_env,
    truncate_output,
)
from src.safety.policy import (
    Decision,
    Policy,
    confirm,
    decide,
    default_policy_path,
    load_policy,
)

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
    truncated: bool = False


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
    max_output_bytes: int | None = None,
) -> RunResult:
    """Decide com a safety, confirma se preciso, e só então executa."""

    root = Path(project_root) if project_root is not None else default_policy_path().parents[1]
    active_policy = policy if policy is not None else load_policy(default_policy_path())
    workdir = Path(cwd) if cwd is not None else root
    decision = decide(
        command,
        policy=active_policy,
        project_root=root,
        workdir=workdir,
    )

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

    if not decision.argv:
        output_fn("sem argv autorizado; não executado.")
        return RunResult(
            decision=decision,
            approved=True,
            executed=False,
            exit_code=None,
            stdout="",
            stderr="",
        )

    try:
        effective_timeout = normalize_timeout(timeout)
        out_limit = (
            max_output_bytes
            if max_output_bytes is not None
            else output_max_bytes_from_env()
        )
        assert_not_generated_execution(
            argv=list(decision.argv),
            workdir=Path(decision.workdir),
        )
    except RunnerLimitError as exc:
        output_fn(str(exc))
        return RunResult(
            decision=decision,
            approved=True,
            executed=False,
            exit_code=None,
            stdout="",
            stderr=str(exc),
        )

    execute = runner or _default_runner

    try:
        completed = execute(
            decision.argv,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            cwd=decision.workdir,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, trunc_out = truncate_output(_as_text(exc.stdout), max_bytes=out_limit)
        stderr, trunc_err = truncate_output(_as_text(exc.stderr), max_bytes=out_limit)
        if not stderr:
            stderr = f"timeout após {effective_timeout:g}s"
        return RunResult(
            decision=decision,
            approved=True,
            executed=True,
            exit_code=None,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
            truncated=trunc_out or trunc_err,
        )

    stdout, trunc_out = truncate_output(completed.stdout or "", max_bytes=out_limit)
    stderr, trunc_err = truncate_output(completed.stderr or "", max_bytes=out_limit)
    return RunResult(
        decision=decision,
        approved=True,
        executed=True,
        exit_code=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        truncated=trunc_out or trunc_err,
    )


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
