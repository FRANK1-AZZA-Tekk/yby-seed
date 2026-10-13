"""Sistema mínimo e seguro de skills do YBY SEED."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    requires_confirmation: bool
    handler: Callable[[dict[str, str]], str]


def _echo(args: dict[str, str]) -> str:
    return args.get("message", "")


def _read_doc(args: dict[str, str]) -> str:
    name = args.get("name", "README")
    path = Path("docs") / f"{name}.md"
    if not path.is_file():
        path = Path(f"{name}.md")
    if not path.is_file():
        raise FileNotFoundError(f"Documento não encontrado: {name}")
    return path.read_text(encoding="utf-8")[:1000]


REGISTRY: dict[str, Skill] = {
    "echo": Skill(
        name="echo",
        description="Retorna uma mensagem informada.",
        requires_confirmation=False,
        handler=_echo,
    ),
    "read_doc": Skill(
        name="read_doc",
        description="Lê um documento Markdown local.",
        requires_confirmation=False,
        handler=_read_doc,
    ),
}


def list_skills() -> list[Skill]:
    return sorted(REGISTRY.values(), key=lambda skill: skill.name)


def run_skill(name: str, args: dict[str, str] | None = None, confirm: bool = False) -> str:
    skill = REGISTRY.get(name)
    if skill is None:
        raise KeyError(f"Skill não encontrada: {name}")
    if skill.requires_confirmation and not confirm:
        raise PermissionError(f"A skill '{name}' exige confirmação explícita (--yes).")
    return skill.handler(args or {})
