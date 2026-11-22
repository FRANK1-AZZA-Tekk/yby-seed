"""Camada C — esqueleto: descoberta de skills + dry-run (sem execução)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillSummary:
    """Resumo honesto de uma skill descoberta (sem carregar código executável)."""

    name: str
    description: str
    directory: Path
    scripts: tuple[Path, ...]
    compatibility: str = ""


@dataclass(frozen=True)
class DryRunPreview:
    """Pré-visualização dry-run — nunca implica execução."""

    skill: SkillSummary
    request: str
    steps: tuple[str, ...]
    would_execute: bool = False
    message: str = (
        "DRY-RUN: nenhum código seria executado. "
        "Confirmação humana obrigatória; auto-run não implementado."
    )


class AutoRunRefused(RuntimeError):
    """Execução automática recusada — política da Camada C."""


def refuse_auto_run(skill_name: str) -> None:
    """Recusa execução automática de forma explícita."""
    raise AutoRunRefused(
        f"Execução automática recusada para {skill_name!r}. "
        "A Camada C só oferece dry-run + confirmação humana; o executor ainda não existe."
    )


def request_human_confirm(*, auto: bool = False, skill_name: str = "") -> bool:
    """Confirmação humana.

    - auto=True → sempre False (política: sem auto-run).
    - auto=False → stub: retorna False até existir fluxo interativo real.
    """
    if auto:
        return False
    _ = skill_name
    return False


def _thin_read_skill(skill_md: Path, skill_dir: Path) -> SkillSummary | None:
    """Leitor mínimo de frontmatter, sem depender do YAML completo."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return SkillSummary(
            name=skill_dir.name,
            description="(frontmatter ausente)",
            directory=skill_dir,
            scripts=tuple((skill_dir / "scripts").glob("*.py"))
            if (skill_dir / "scripts").is_dir()
            else (),
        )

    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    name = skill_dir.name
    description = "(metadados parciais — YAML inválido no SKILL.md)"
    compatibility = ""
    for line in parts[1].splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            name = stripped[5:].strip().strip("\"'") or name
        elif stripped.startswith("description:"):
            description = stripped[12:].strip().strip("\"'") or description
        elif stripped.startswith("compatibility:"):
            compatibility = stripped[14:].strip().strip("\"'")
    scripts_dir = skill_dir / "scripts"
    scripts = tuple(scripts_dir.glob("*.py")) if scripts_dir.is_dir() else ()
    return SkillSummary(
        name=name,
        description=description,
        directory=skill_dir,
        scripts=scripts,
        compatibility=compatibility,
    )


class SkillsDryRun:
    """Descoberta de skills e prévia dry-run, sem execução de código."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)

    def discover(self) -> list[SkillSummary]:
        """Descobre skills a partir de SKILL.md, com fallback para YAML inválido."""
        if not self.skills_dir.is_dir():
            return []

        found: dict[str, SkillSummary] = {}
        for skill_dir in sorted(self.skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue
            summary = _thin_read_skill(skill_md, skill_dir)
            if summary is not None and summary.name not in found:
                found[summary.name] = summary
        return sorted(found.values(), key=lambda item: item.name)

    def preview(self, skill_name: str, request: str = "") -> DryRunPreview:
        """Monta prévia dry-run; não executa scripts nem gera código."""
        found = {item.name: item for item in self.discover()}
        skill = found.get(skill_name)
        if skill is None:
            raise KeyError(skill_name)

        steps: list[str] = [
            f"1. Carregar metadados de {skill.directory / 'SKILL.md'}",
            f"2. Pedido do usuário: {request or '(nenhum)'}",
            "3. Gerar plano / código (ainda não implementado)",
            "4. Mostrar diff e pedir confirmação humana",
            "5. Só então executar — BLOQUEADO neste esqueleto",
        ]
        if skill.scripts:
            listed = ", ".join(item.name for item in skill.scripts)
            steps.insert(2, f"Scripts presentes (não executados): {listed}")

        return DryRunPreview(
            skill=skill,
            request=request,
            steps=tuple(steps),
        )
