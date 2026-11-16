"""Decisão pura sobre um comando. Não executa nada."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

Action = Literal["run", "ask", "refuse"]
_INTERPRETERS = frozenset({"python", "python3", "bash", "sh"})
_YES = frozenset({"s", "sim", "y", "yes"})
# Subcomandos git de inspeção. O resto de `git` pede confirmação.
_SAFE_GIT_SUBCOMMANDS = frozenset(
    {
        "status",
        "diff",
        "log",
        "show",
        "branch",
        "rev-parse",
        "describe",
    }
)
# Opções globais que mudam repo, config ou tools externos → não auto-executar.
_GIT_ASK_GLOBALS = frozenset(
    {
        "-c",
        "-C",
        "--git-dir",
        "--work-tree",
        "--namespace",
        "--config-env",
        "--exec-path",
        "--super-prefix",
    }
)
_GIT_VALUE_GLOBALS = frozenset(
    {
        "-c",
        "-C",
        "--git-dir",
        "--work-tree",
        "--namespace",
        "--config-env",
        "--exec-path",
        "--super-prefix",
    }
)
_GIT_BRANCH_MUTATING = frozenset(
    {
        "-d",
        "-D",
        "-m",
        "-M",
        "-c",
        "-C",
        "--delete",
        "--move",
        "--copy",
        "--create-reflog",
    }
)


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
    argv: tuple[str, ...] = ()
    workdir: str = ""


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


def decide(
    command: str,
    *,
    policy: Policy,
    project_root: Path,
    workdir: Path | None = None,
) -> Decision:
    """Classifica o comando. `project_root` limita os scripts permitidos.

    `workdir` é o diretório que o executor usará; fica gravado na Decision
    junto com o argv tokenizado (um único shlex).
    """

    work = str((workdir if workdir is not None else project_root).resolve())

    def finish(
        action: Action,
        reason: str,
        argv: tuple[str, ...] | list[str] = (),
    ) -> Decision:
        return Decision(action, reason, argv=tuple(argv), workdir=work)

    raw = command.strip()
    if not raw:
        return finish("refuse", "comando vazio")

    try:
        argv = shlex.split(raw, posix=True)
    except ValueError as exc:
        refused = _refuse_hit(raw, (), policy)
        if refused is not None:
            return finish("refuse", f"padrão destrutivo: {refused}")
        if _has_shell_glue(raw):
            return finish("ask", "comando com encadeamento de shell")
        return finish("ask", f"não deu para separar o comando: {exc}")

    if not argv:
        return finish("refuse", "comando vazio")

    argv_t = tuple(argv)
    refused = _refuse_hit(raw, argv, policy)
    if refused is not None:
        return finish("refuse", f"padrão destrutivo: {refused}", argv_t)

    if _has_shell_glue(raw):
        return finish("ask", "comando com encadeamento de shell", argv_t)

    program = _bare_program(argv[0])
    if program is None:
        named = Path(argv[0]).name
        if named in policy.read_only or named in policy.git:
            return finish(
                "ask",
                "executável com caminho não é confiável só pelo nome",
                argv_t,
            )
        script = _project_script(argv, policy, project_root)
        if script is not None:
            return finish(
                "ask",
                f"script do projeto pede confirmação: {script}",
                argv_t,
            )
        return finish("ask", "fora da allowlist", argv_t)

    if program in policy.read_only:
        inner = _decide_read(program, argv[1:])
        return finish(inner.action, inner.reason, argv_t)

    if program in policy.git:
        inner = _decide_git(argv, policy)
        return finish(inner.action, inner.reason, argv_t)

    script = _project_script(argv, policy, project_root)
    if script is not None:
        return finish(
            "ask",
            f"script do projeto pede confirmação: {script}",
            argv_t,
        )

    return finish("ask", "fora da allowlist", argv_t)


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
    try:
        answer = input_fn().strip().casefold()
    except (EOFError, OSError):
        output_fn("Sem interação; não executado.")
        return False
    if answer in _YES:
        return True
    output_fn("Não executado.")
    return False


def _bare_program(argv0: str) -> str | None:
    """Só confia no token sem path (não basename de ./git ou /tmp/git)."""

    if not argv0 or argv0 in {".", ".."}:
        return None
    if "/" in argv0 or "\\" in argv0 or argv0.startswith("~"):
        return None
    if Path(argv0).name != argv0:
        return None
    return argv0


def _decide_read(program: str, args: list[str]) -> Decision:
    """[read] autoriza o binário, mas opções mutáveis pedem confirmação."""

    if program == "date" and _date_mutates(args):
        return Decision("ask", "date com alteração de relógio")
    return Decision("run", f"comando somente leitura: {program}")


def _date_mutates(args: list[str]) -> bool:
    for arg in args:
        if arg in {"-s", "--set"} or arg.startswith("--set="):
            return True
    return False


def _matches_refuse(raw: str, argv: tuple[str, ...] | list[str], pattern: str) -> bool:
    if _contains_pattern(raw, pattern):
        return True
    if argv and _contains_pattern(" ".join(argv), pattern):
        return True
    for arg in argv:
        if _contains_pattern(arg, pattern):
            return True
    return False


def _refuse_hit(
    raw: str,
    argv: tuple[str, ...] | list[str],
    policy: Policy,
) -> str | None:
    """Casa [refuse] no texto cru e no argv já tokenizado (aspas removidas)."""

    for pattern in policy.refuse:
        if _matches_refuse(raw, argv, pattern):
            return pattern
    return None


def _decide_git(argv: list[str], policy: Policy) -> Decision:
    """Git: só inspeção allowlisted sem globals arriscados; resto ask/refuse."""

    args = argv[1:]
    if any("!" in arg for arg in args):
        return Decision("refuse", "git com execução via alias/shell")

    parsed = _parse_git_args(args)
    if parsed.ask_reason is not None:
        return Decision("ask", parsed.ask_reason)

    subcommand = parsed.subcommand
    rest = parsed.rest
    if subcommand is None:
        return Decision("ask", "git sem subcomando claro")

    # Recusa estrutural (não só substring no comando cru).
    destructive = _git_destructive(subcommand, rest)
    if destructive is not None:
        return Decision("refuse", destructive)

    normalized_argv = ["git", subcommand, *rest]
    refused = _refuse_hit(" ".join(normalized_argv), normalized_argv, policy)
    if refused is not None:
        return Decision("refuse", f"padrão destrutivo: {refused}")

    if subcommand == "config":
        return Decision("ask", "git config pede confirmação")

    if subcommand in _SAFE_GIT_SUBCOMMANDS:
        if subcommand == "branch" and _branch_mutates(rest):
            return Decision("ask", "git branch mutável pede confirmação")
        return Decision("run", f"comando git: {subcommand}")

    return Decision("ask", f"git {subcommand} pede confirmação")


@dataclass(frozen=True)
class _GitParse:
    ask_reason: str | None
    subcommand: str | None
    rest: tuple[str, ...]


def _parse_git_args(args: list[str]) -> _GitParse:
    """Separa opções globais do subcomando; globals arriscados → ask_reason."""

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            i += 1
            break

        key, inline_value = _git_option_key(arg)
        if key in _GIT_ASK_GLOBALS:
            if key in {"-c", "--config-env"}:
                return _GitParse("git com configuração inline", None, ())
            return _GitParse("git com repositório/tool path alternativo", None, ())

        if arg in _GIT_VALUE_GLOBALS:
            i += 2
            continue
        if inline_value:
            i += 1
            continue
        if arg.startswith("-"):
            # --no-pager, --paginate, etc. são só UX; seguem.
            i += 1
            continue

        return _GitParse(None, arg.casefold(), tuple(args[i + 1 :]))

    if i < len(args) and not args[i].startswith("-"):
        return _GitParse(None, args[i].casefold(), tuple(args[i + 1 :]))
    return _GitParse(None, None, ())


def _git_option_key(arg: str) -> tuple[str | None, bool]:
    """Retorna (chave da opção, tem valor inline com =)."""

    if arg in _GIT_VALUE_GLOBALS or arg in _GIT_ASK_GLOBALS:
        return arg, False
    for prefix in (
        "--git-dir=",
        "--work-tree=",
        "--namespace=",
        "--config-env=",
        "--exec-path=",
        "--super-prefix=",
    ):
        if arg.startswith(prefix):
            return prefix[:-1], True
    return None, False


def _git_destructive(subcommand: str, rest: tuple[str, ...]) -> str | None:
    if subcommand == "reset" and "--hard" in rest:
        return "git reset --hard recusado"
    if subcommand == "clean" and _clean_force(rest):
        return "git clean forçado recusado"
    if subcommand == "push" and _push_force(rest):
        return "git push --force recusado"
    return None


def _clean_force(rest: tuple[str, ...]) -> bool:
    joined = " ".join(rest)
    if "-fd" in rest or "-xfd" in rest or "-fxd" in rest:
        return True
    # -f combinado em cluster curto (ex.: -ffd já coberto; -f -d)
    if "-f" in rest or "--force" in rest:
        return True
    if "fd" in joined.replace(" ", "") and any(a.startswith("-") and "f" in a for a in rest):
        return True
    return False


def _push_force(rest: tuple[str, ...]) -> bool:
    return any(
        arg in {"--force", "-f"} or arg.startswith("--force-with-lease") for arg in rest
    )


def _branch_mutates(rest: tuple[str, ...]) -> bool:
    return any(arg in _GIT_BRANCH_MUTATING for arg in rest)


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
