"""Camada C — esqueleto: descoberta de skills + dry-run (sem execução)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from src.app.layers import Layer

if TYPE_CHECKING:
    from src.app.kernel import App


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
    would_execute: bool = False  # sempre False neste esqueleto
    message: str = (
        "DRY-RUN: nenhum código seria executado. "
        "Confirmação humana obrigatória; auto-run não implementado."
    )


class AutoRunRefused(RuntimeError):
    """Execução automática recusada — política da Camada C."""


def refuse_auto_run(skill_name: str) -> None:
    """Stub de confirmação humana: sempre recusa auto-run."""
    raise AutoRunRefused(
        f"Execução automática recusada para {skill_name!r}. "
        "Camada C só oferece dry-run + confirmação humana; o executor ainda não existe."
    )


def request_human_confirm(*, auto: bool = False, skill_name: str = "") -> bool:
    """Confirmação humana.

    - auto=True → sempre False (política: sem auto-run).
    - auto=False → stub: retorna False até existir fluxo interativo real.
    """
    if auto:
        return False
    # Esqueleto: sem prompt interativo de execução ainda.
    _ = skill_name
    return False


def _thin_read_skill(skill_md: Path, skill_dir: Path) -> SkillSummary | None:
    """Leitor mínimo de frontmatter (name/description) sem depender do YAML completo."""
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


class SkillsLayer:
    """Plugin Camada C: /skills (lista) e /skill (dry-run preview)."""

    layer: Layer = Layer.SKILLS
    name: str = "skills"

    def register(self, app: App) -> None:
        app.register_command("skills", _cmd_skills)
        app.register_command("skill", _cmd_skill)

    def skills_dir(self, app: App) -> Path:
        return Path(app.settings.project_root) / "skills"

    def discover(self, skills_dir: Path) -> list[SkillSummary]:
        """Descobre skills via SkillManager; fallback thin reader se YAML falhar."""
        from src.skills.skill_manager import SkillManager

        if not skills_dir.is_dir():
            return []

        manager = SkillManager(str(skills_dir))
        manager.discover_skills()
        by_name: dict[str, SkillSummary] = {}
        for skill in manager.skills.values():
            directory = skill.metadata.directory or skills_dir
            scripts = tuple(skill.get_scripts())
            by_name[skill.metadata.name] = SkillSummary(
                name=skill.metadata.name,
                description=skill.metadata.description or "(sem descrição)",
                directory=Path(directory),
                scripts=scripts,
                compatibility=skill.metadata.compatibility or "",
            )

        # Pastas com SKILL.md que o SkillManager não carregou (YAML inválido, etc.)
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue
            if any(s.directory.resolve() == skill_dir.resolve() for s in by_name.values()):
                continue
            thin = _thin_read_skill(skill_md, skill_dir)
            if thin is not None and thin.name not in by_name:
                by_name[thin.name] = thin

        return sorted(by_name.values(), key=lambda s: s.name)

    def preview(
        self,
        skills_dir: Path,
        skill_name: str,
        request: str = "",
    ) -> DryRunPreview:
        """Monta preview dry-run; não executa scripts nem gera código."""
        found = {s.name: s for s in self.discover(skills_dir)}
        skill = found.get(skill_name)
        if skill is None:
            raise KeyError(skill_name)

        steps: tuple[str, ...] = (
            f"1. Carregar metadados de {skill.directory / 'SKILL.md'}",
            f"2. Pedido do usuário: {request or '(nenhum)'}",
            "3. Gerar plano / código (ainda não implementado)",
            "4. Mostrar diff e pedir confirmação humana",
            "5. Só então executar — BLOQUEADO neste esqueleto",
        )
        if skill.scripts:
            listed = ", ".join(p.name for p in skill.scripts)
            steps = (*steps[:2], f"Scripts presentes (não executados): {listed}", *steps[2:])

        return DryRunPreview(skill=skill, request=request, steps=steps)


def _cmd_skills(app: App, args: list[str]) -> int:
    """Lista skills descobertas em skills/."""
    layer = SkillsLayer()
    skills_dir = layer.skills_dir(app)

    if args and args[0].lower() in {"run", "exec", "execute"}:
        name = args[1] if len(args) > 1 else "?"
        app.stderr.write(
            f"ERRO: execução recusada ({name!r}). Use /skill <nome> para dry-run.\n"
        )
        return 2

    if not skills_dir.is_dir():
        app.stderr.write(f"ERRO: diretório de skills ausente: {skills_dir}\n")
        return 1

    summaries = layer.discover(skills_dir)
    mode = app.settings.skills_mode
    app.stdout.write(f"Skills descobertas ({len(summaries)}) — modo: {mode}\n")
    if not summaries:
        app.stdout.write("(nenhuma SKILL.md encontrada)\n")
        return 0

    for item in summaries:
        n_scripts = len(item.scripts)
        app.stdout.write(
            f"  • {item.name}: {item.description[:80]}"
            f"{'…' if len(item.description) > 80 else ''}"
            f" [{n_scripts} script(s)]\n"
        )
    app.stdout.write(
        "Dry-run: /skill <nome> [pedido]\n"
        "Execução de código: não disponível (confirmação humana obrigatória).\n"
    )
    return 0


def _cmd_skill(app: App, args: list[str]) -> int:
    """Dry-run preview de uma skill; recusa qualquer pedido de execução."""
    if not args:
        app.stderr.write("Uso: /skill <nome> [pedido…]   |  /skills para listar\n")
        return 2

    if args[0].lower() in {"run", "exec", "execute"}:
        name = args[1] if len(args) > 1 else "?"
        try:
            refuse_auto_run(name)
        except AutoRunRefused as exc:
            app.stderr.write(f"ERRO: {exc}\n")
        return 2

    skill_name = args[0]
    request = " ".join(args[1:]).strip()
    layer = SkillsLayer()
    skills_dir = layer.skills_dir(app)

    # Flags honestas de execução → recusa
    if "--run" in args or "--execute" in args or "-x" in args:
        try:
            refuse_auto_run(skill_name)
        except AutoRunRefused as exc:
            app.stderr.write(f"ERRO: {exc}\n")
        return 2

    if not request_human_confirm(auto=False, skill_name=skill_name):
        # esperado no esqueleto — seguimos só com preview
        pass

    try:
        preview = layer.preview(skills_dir, skill_name, request=request)
    except KeyError:
        app.stderr.write(
            f"ERRO: skill {skill_name!r} não encontrada. Use /skills.\n"
        )
        return 2

    assert preview.would_execute is False
    app.stdout.write(f"=== DRY-RUN: {preview.skill.name} ===\n")
    app.stdout.write(f"Descrição: {preview.skill.description}\n")
    if preview.skill.compatibility:
        app.stdout.write(f"Compat: {preview.skill.compatibility}\n")
    app.stdout.write(f"Dir: {preview.skill.directory}\n")
    for step in preview.steps:
        app.stdout.write(f"  {step}\n")
    app.stdout.write(f"{preview.message}\n")
    return 0
