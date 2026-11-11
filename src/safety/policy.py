"""Decisão pura sobre um comando. Não executa nada."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

Action = Literal["run", "ask", "refuse"]
_INTERPRETERS = frozenset({"python", "python3", "bash", "sh"})
_YES = frozenset({"s", "sim", "y", "yes"})


@dataclass(frozen=True)
class Policy:
    """Listas lidas do arquivo de allowlist."""

    read_only: frozenset[str]
    git: frozenset[str]
    script_dirs: tuple[str, ...]
    refuse: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    """O que fazer com o comando."""

    action: Action
    reason: str


def load_policy(path: Path) -> Policy:
    """Lê a allowlist. Seções desconhecidas são ignoradas."""

    read_only: list[str] = []
    git: list[str] = []
    script_dirs: list[str] = []
    refuse: list[str] = []
    section = ""
    buckets = {
        "read": read_only,
        "git": git,
        "scripts": script_dirs,
        "refuse": refuse,
    }

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().casefold()
            continue
        bucket = buckets.get(section)
        if bucket is not None:
            bucket.append(line)

    return Policy(
        read_only=frozenset(read_only),
        git=frozenset(git),
        script_dirs=tuple(script_dirs),
        refuse=tuple(refuse),
    )


def default_policy_path() -> Path:
    """Arquivo versionado na raiz do repositório."""

    return Path(__file__).resolve().parents[2] / "config" / "safety-allowlist.txt"


def decide(command: str, *, policy: Policy, project_root: Path) -> Decision:
    """Classifica o comando. `project_root` limita os scripts permitidos."""

    raw = command.strip()
    if not raw:
        return Decision("refuse", "comando vazio")

    for pattern in policy.refuse:
        if _contains_pattern(raw, pattern):
            return Decision("refuse", f"padrão destrutivo: {pattern}")

    if _has_shell_glue(raw):
        return Decision("ask", "comando com encadeamento de shell")

    try:
        argv = shlex.split(raw, posix=True)
    except ValueError as exc:
        return Decision("ask", f"não deu para separar o comando: {exc}")

    if not argv:
        return Decision("refuse", "comando vazio")

    program = Path(argv[0]).name
    if program in policy.read_only:
        return Decision("run", f"comando somente leitura: {program}")

    if program in policy.git:
        return Decision("run", f"comando git: {program}")

    script = _project_script(argv, policy, project_root)
    if script is not None:
        return Decision("run", f"script do projeto: {script}")

    return Decision("ask", "fora da allowlist")


def confirm(
    command: str,
    decision: Decision,
    *,
    input_fn: Callable[[], str] = input,
    output_fn: Callable[[str], None] = print,
) -> bool:
    """Pede sim/não só quando a decisão é ask. Não executa o comando."""

    if decision.action == "run":
        return True
    if decision.action == "refuse":
        output_fn(decision.reason)
        return False

    output_fn(f"Executar `{command}`? [s/n]")
    answer = input_fn().strip().casefold()
    if answer in _YES:
        return True
    output_fn("Não executado.")
    return False


def _contains_pattern(command: str, pattern: str) -> bool:
    haystack = " ".join(command.split()).casefold()
    needle = " ".join(pattern.split()).casefold()
    start = 0
    while True:
        index = haystack.find(needle, start)
        if index < 0:
            return False
        after = index + len(needle)
        if after >= len(haystack) or haystack[after].isspace():
            return True
        start = index + 1


def _has_shell_glue(command: str) -> bool:
    return any(token in command for token in ("|", ";", "`", "\n")) or any(
        token in command for token in ("&&", "||", "$(")
    )


def _project_script(argv: list[str], policy: Policy, project_root: Path) -> Path | None:
    candidate: str | None = None
    program = Path(argv[0]).name
    if program in _INTERPRETERS and len(argv) >= 2 and not argv[1].startswith("-"):
        candidate = argv[1]
    elif "/" in argv[0] or argv[0].endswith((".py", ".sh")):
        candidate = argv[0]

    if candidate is None:
        return None

    root = project_root.resolve()
    path = Path(candidate)
    if not path.is_absolute():
        path = root / path
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None

    if not resolved.is_file():
        return None

    relative = resolved.relative_to(root)
    if not relative.parts:
        return None
    if policy.script_dirs and relative.parts[0] not in policy.script_dirs:
        return None
    return resolved
