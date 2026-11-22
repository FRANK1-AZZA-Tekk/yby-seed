"""CLI de skills em dry-run (Camada C esqueleto)."""

from __future__ import annotations

from pathlib import Path

import click

from src.skills.dry_run import AutoRunRefused, SkillsDryRun, refuse_auto_run


@click.group()
def skills() -> None:
    """Lista skills ou mostra prévia dry-run (sem execução)."""


@skills.command("list")
@click.option(
    "--skills-dir",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    default=Path("skills"),
    show_default=True,
    help="Diretório contendo pastas de skills.",
)
def list_skills(skills_dir: Path) -> None:
    """Lista skills descobertas em SKILL.md."""
    layer = SkillsDryRun(skills_dir)
    summaries = layer.discover()
    click.echo(f"Skills descobertas ({len(summaries)})")
    if not summaries:
        click.echo("(nenhuma SKILL.md encontrada)")
        return
    for item in summaries:
        description = item.description[:80]
        suffix = "…" if len(item.description) > 80 else ""
        click.echo(f"  • {item.name}: {description}{suffix} [{len(item.scripts)} script(s)]")
    click.echo("Dry-run: yby skills preview <nome> [pedido]")
    click.echo("Execução de código: não disponível (confirmação humana obrigatória).")


@skills.command("preview")
@click.argument("skill_name")
@click.argument("request", nargs=-1)
@click.option(
    "--skills-dir",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    default=Path("skills"),
    show_default=True,
    help="Diretório contendo pastas de skills.",
)
def preview_skill(skill_name: str, request: tuple[str, ...], skills_dir: Path) -> None:
    """Mostra prévia dry-run de uma skill; recusa execução."""
    if skill_name.lower() in {"run", "exec", "execute"}:
        try:
            refuse_auto_run(skill_name)
        except AutoRunRefused as exc:
            click.echo(f"ERRO: {exc}", err=True)
        raise SystemExit(2)

    layer = SkillsDryRun(skills_dir)
    try:
        preview = layer.preview(skill_name, request=" ".join(request).strip())
    except KeyError:
        click.echo(f"ERRO: skill {skill_name!r} não encontrada. Use 'yby skills list'.", err=True)
        raise SystemExit(2)

    click.echo(f"=== DRY-RUN: {preview.skill.name} ===")
    click.echo(f"Descrição: {preview.skill.description}")
    if preview.skill.compatibility:
        click.echo(f"Compat: {preview.skill.compatibility}")
    click.echo(f"Dir: {preview.skill.directory}")
    for step in preview.steps:
        click.echo(f"  {step}")
    click.echo(preview.message)
