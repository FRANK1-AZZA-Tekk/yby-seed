"""CLI de skills em dry-run (Camada C esqueleto)."""

from __future__ import annotations

from pathlib import Path

import click

from src.skills.dry_run import (
    AutoRunRefused,
    SkillsDryRun,
    refuse_auto_run,
    request_human_confirm,
)


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
    click.echo("Confirmação: yby skills confirm <nome> [pedido]")
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


@skills.command("confirm")
@click.argument("skill_name")
@click.argument("request", nargs=-1)
@click.option(
    "--skills-dir",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    default=Path("skills"),
    show_default=True,
    help="Diretório contendo pastas de skills.",
)
@click.option(
    "--auto",
    is_flag=True,
    default=False,
    help="Tenta execução automática; sempre recusado.",
)
def confirm_skill(
    skill_name: str,
    request: tuple[str, ...],
    skills_dir: Path,
    auto: bool,
) -> None:
    """Solicita confirmação humana antes de uma execução futura."""
    request_text = " ".join(request).strip()

    layer = SkillsDryRun(skills_dir)

    try:
        preview = layer.preview(skill_name, request=request_text)
    except KeyError:
        click.echo(
            f"ERRO: skill {skill_name!r} não encontrada. "
            "Use 'yby skills list'.",
            err=True,
        )
        raise SystemExit(2)

    click.echo(f"=== CONFIRMAÇÃO: {preview.skill.name} ===")
    click.echo(f"Pedido: {request_text or '(nenhum)'}")
    click.echo(f"Scripts encontrados: {len(preview.skill.scripts)}")
    click.echo("Nenhum script será executado nesta etapa.")

    try:
        confirmation = request_human_confirm(
            auto=auto,
            skill_name=skill_name,
            request=request_text,
            prompt=not auto,
        )
    except AutoRunRefused as exc:
        click.echo(f"ERRO: {exc}", err=True)
        raise SystemExit(2)

    if not confirmation.approved:
        click.echo("Execução não aprovada.", err=True)
        raise SystemExit(1)

    click.echo("Aprovação registrada.")
    click.echo(f"ID: {confirmation.confirmation_id}")
    click.echo(f"Aprovada em: {confirmation.approved_at}")
    click.echo(
        "Próximo passo: implementar executor autorizado que valide "
        "o briefing e execute apenas após esta confirmação."
    )
