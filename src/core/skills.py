"""Sistema mínimo e seguro de skills do YBY SEED."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


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
    if not _SAFE_NAME.fullmatch(name):
        raise ValueError("Nome de documento inválido.")
    docs_root = Path("docs").resolve()
    path = (docs_root / f"{name}.md").resolve()
    if not path.is_relative_to(docs_root):
        raise ValueError("Acesso fora do diretório docs/ não é permitido.")
    if not path.is_file():
        raise FileNotFoundError(f"Documento não encontrado: {name}")
    return path.read_text(encoding="utf-8")[:1000]


def _write_note(args: dict[str, str]) -> str:
    title = args.get("title", "note")
    content = args.get("content", "")
    if not _SAFE_NAME.fullmatch(title):
        raise ValueError("Título de nota inválido.")
    notes_root = Path(".yby/notes").resolve()
    notes_root.mkdir(parents=True, exist_ok=True)
    path = (notes_root / f"{title}.md").resolve()
    if not path.is_relative_to(notes_root):
        raise ValueError("Acesso fora do diretório de notas não é permitido.")
    path.write_text(content, encoding="utf-8")
    return f"Nota salva em {path}"


REGISTRY: dict[str, Skill] = {
    "echo": Skill(
        name="echo",
        description="Retorna uma mensagem informada.",
        requires_confirmation=False,
        handler=_echo,
    ),
    "read_doc": Skill(
        name="read_doc",
        description="Lê um documento Markdown permitido em docs/.",
        requires_confirmation=False,
        handler=_read_doc,
    ),
    "write_note": Skill(
        name="write_note",
        description="Salva uma nota local em .yby/notes/.",
        requires_confirmation=True,
        handler=_write_note,
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
