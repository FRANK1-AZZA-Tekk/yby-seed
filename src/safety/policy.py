"""Decisão pura sobre um comando. Não executa nada."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Callable, Literal

Action = Literal["run", "ask", "refuse"]
_INTERPRETERS = frozenset({"python", "python3", "bash", "sh"})
_YES = frozenset({"s", "sim", "y", "yes"})

# Programas da seção [read] que despejam o conteúdo dos arquivos recebidos.
_CONTENT_READERS = frozenset({"cat", "head", "tail"})
_PATH_EXPANSION_CHARS = "$*?["

# Piso fixo: vale mesmo se a allowlist não tiver a seção [sensitive].
# Casa com cada componente do caminho (sem diferenciar maiúsculas) ou, se o
# padrão tiver "/", com o caminho relativo inteiro. A seção [sensitive] só amplia.
_SENSITIVE_FLOOR = (
    ".env",
    ".env.*",
    "*.env",
    "id_rsa*",
    "id_dsa*",
    "id_ecdsa*",
    "id_ed25519*",
    "*.pem",
    "*.key",
    "shadow",
    "shadow-",
    "gshadow",
    ".ssh",
    "credentials",
    "credentials.*",
)

# Opções globais do git que executam código ou trocam a configuração.
_GIT_RISKY_GLOBAL_OPTIONS = frozenset({"-c", "--config-env", "--exec-path"})

SKILL_ACTIONS = frozenset(
    {
        "copy_files_to_backup_dir",
    }
)


@dataclass(frozen=True)
class Policy:
    """Listas lidas do arquivo de allowlist."""

    read_only: frozenset[str]
    git: frozenset[str]
    script_dirs: tuple[str, ...]
    refuse: tuple[str, ...]
    sensitive: tuple[str, ...] = ()


@dataclass(frozen=True)
class Decision:
    """O que fazer com o comando."""

    action: Action
    reason: str


def is_allowed_skill_action(action: str) -> bool:
    """Decide se uma ação declarada por uma skill está na allowlist."""

    return action in SKILL_ACTIONS


def load_policy(path: Path) -> Policy:
    """Lê a allowlist. Seções desconhecidas são ignoradas."""

    read_only: list[str] = []
    git: list[str] = []
    script_dirs: list[str] = []
    refuse: list[str] = []
    sensitive: list[str] = []
    section = ""
    buckets = {
        "read": read_only,
        "git": git,
        "scripts": script_dirs,
        "refuse": refuse,
        "sensitive": sensitive,
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
        sensitive=tuple(sensitive),
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

    try:
        argv = shlex.split(raw, posix=True)
    except ValueError as exc:
        return Decision("ask", f"não deu para separar o comando: {exc}")

    if not argv:
        return Decision("refuse", "comando vazio")

    if Path(argv[0]).name == "git":
        for pattern in policy.refuse:
            if _git_refuse_match(argv, pattern):
                return Decision("refuse", f"padrão destrutivo: {pattern}")

    if _has_shell_glue(raw):
        return Decision("ask", "comando com encadeamento de shell")

    program = Path(argv[0]).name
    if program in policy.read_only:
        if program in _CONTENT_READERS:
            risk = _reader_risk(argv, policy, project_root)
            if risk is not None:
                return Decision("ask", risk)
        return Decision("run", f"comando somente leitura: {program}")

    if program in policy.git:
        sub = _git_subcommand(argv)
        if sub in _GIT_READ_ONLY:
            risk = _git_read_risk(argv, policy)
            if risk is not None:
                return Decision("ask", risk)
            return Decision("run", f"git somente leitura: {sub}")
        return Decision("ask", f"git altera repositório: {sub or program}")

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


_GIT_READ_ONLY = frozenset(
    {
        "status",
        "diff",
        "log",
        "show",
        "rev-parse",
        "ls-files",
        "blame",
        "shortlog",
        "describe",
        "grep",
        "check-ignore",
    }
)


def _sensitive_patterns(policy: Policy) -> tuple[str, ...]:
    return _SENSITIVE_FLOOR + policy.sensitive


def _sensitive_match(parts: tuple[str, ...], policy: Policy) -> str | None:
    """Devolve o padrão sensível que casa com o caminho relativo, se houver."""

    folded = tuple(part.casefold() for part in parts if part not in ("", "."))
    whole = "/".join(folded)
    for pattern in _sensitive_patterns(policy):
        wanted = pattern.casefold()
        if "/" in wanted:
            if fnmatchcase(whole, wanted):
                return pattern
        elif any(fnmatchcase(part, wanted) for part in folded):
            return pattern
    return None


def _relative_parts(path: Path, root: Path) -> tuple[str, ...] | None:
    try:
        return path.relative_to(root).parts
    except ValueError:
        return None


def _reader_risk(argv: list[str], policy: Policy, project_root: Path) -> str | None:
    """Motivo para pedir confirmação em cat/head/tail, ou None se seguro.

    Regra estrutural: todo argumento que não é opção precisa ficar dentro do
    projeto (seguindo links simbólicos) e não casar com um padrão sensível.
    """

    root = project_root.resolve()
    after_dashes = False
    for token in argv[1:]:
        if not after_dashes and token == "--":
            after_dashes = True
            continue
        if not after_dashes and (token.startswith("-") or not token):
            continue
        if any(char in token for char in _PATH_EXPANSION_CHARS):
            return f"caminho com expansão de shell: {token}"
        expanded = Path(os.path.expanduser(token))
        candidate = expanded if expanded.is_absolute() else root / expanded
        try:
            resolved = candidate.resolve()
        except (OSError, RuntimeError):
            return f"caminho não resolvido: {token}"
        resolved_parts = _relative_parts(resolved, root)
        if resolved_parts is None:
            return f"arquivo fora do projeto: {token}"
        lexical_parts = _relative_parts(Path(os.path.normpath(candidate)), root)
        for parts in (lexical_parts, resolved_parts):
            if parts is None:
                continue
            pattern = _sensitive_match(parts, policy)
            if pattern is not None:
                return f"arquivo possivelmente sensível ({pattern}): {token}"
    return None


def _git_read_risk(argv: list[str], policy: Policy) -> str | None:
    """Motivo para pedir confirmação num git de leitura, ou None se seguro."""

    index = 1
    while index < len(argv):
        arg = argv[index]
        option = arg.split("=", 1)[0]
        if option in _GIT_OPTIONS_WITH_VALUE:
            if option in _GIT_RISKY_GLOBAL_OPTIONS:
                return f"git com opção global que altera configuração ou executa código: {option}"
            index += 1 if "=" in arg else 2
            continue
        if arg.startswith("-"):
            if option in _GIT_RISKY_GLOBAL_OPTIONS:
                return f"git com opção global que altera configuração ou executa código: {option}"
            index += 1
            continue
        break

    for token in _git_command_tokens(argv)[1:]:
        if token == "--no-index":
            return "git --no-index lê arquivos fora do repositório"
        if token.startswith("--open-files-in-pager") or (
            token.startswith("-O") and not token.startswith("--")
        ):
            return "git abre arquivos num programa externo (-O)"
        if token.startswith("-"):
            continue
        path_part = token.rsplit(":", 1)[-1]
        pattern = _sensitive_match(tuple(path_part.split("/")), policy)
        if pattern is not None:
            return f"git expõe arquivo possivelmente sensível ({pattern}): {token}"
    return None


def _git_subcommand(argv: list[str]) -> str:
    tokens = _git_command_tokens(argv)
    return tokens[0] if tokens else ""


_GIT_OPTIONS_WITH_VALUE = frozenset(
    {
        "-C",
        "-c",
        "--git-dir",
        "--work-tree",
        "--namespace",
        "--config-env",
        "--super-prefix",
        "--list-cmds",
    }
)


def _git_refuse_match(argv: list[str], pattern: str) -> bool:
    """Casa padrões `git ...` mesmo com flags fora de ordem ou opções globais."""

    if Path(argv[0]).name != "git":
        return False
    try:
        wanted_argv = shlex.split(pattern, posix=True)
    except ValueError:
        return False
    if not wanted_argv or Path(wanted_argv[0]).name != "git":
        return False
    actual = _git_command_tokens(argv)
    wanted = _git_command_tokens(wanted_argv)
    if not actual or not wanted or actual[0] != wanted[0]:
        return False
    return all(_git_token_present(token, actual[1:]) for token in wanted[1:])


def _git_command_tokens(argv: list[str]) -> list[str]:
    tokens: list[str] = []
    index = 1
    while index < len(argv):
        arg = argv[index]
        option = arg.split("=", 1)[0]
        if option in _GIT_OPTIONS_WITH_VALUE:
            index += 1 if "=" in arg else 2
            continue
        if arg == "--":
            tokens.extend(argv[index + 1 :])
            break
        tokens.append(arg)
        index += 1
    return tokens


def _git_token_present(wanted: str, actual: list[str]) -> bool:
    if wanted in actual:
        return True
    if not wanted.startswith("-") or wanted.startswith("--"):
        return False
    letters = set(wanted[1:])
    if not letters:
        return False
    found: set[str] = set()
    for token in actual:
        if token.startswith("-") and not token.startswith("--"):
            found.update(token[1:])
    return letters <= found


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
