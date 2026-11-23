"""Click: yby develop plan|export|send|accept|reject|show."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
from dotenv import load_dotenv


def _repo_root() -> Path:
    return Path.cwd()


def _base_commit(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _develop_root() -> Path | None:
    import os

    raw = (os.environ.get("YBY_DEVELOP_ROOT") or "").strip()
    return Path(raw).expanduser() if raw else None


@click.group("develop")
def develop_cli() -> None:
    """Piloto multi-camada: Ollama → Markdown → Cursor (sem OpenRouter)."""


@develop_cli.command("plan")
@click.argument("pedido")
@click.option("--planner", "planner_name", default="ollama", show_default=True)
def develop_plan(pedido: str, planner_name: str) -> None:
    """Gera plano validado e grava no path do painel."""

    load_dotenv(override=False)
    from src.develop.planner import make_ollama_planner
    from src.develop.store import save_plan
    from src.develop.validate import PlanValidationError

    if planner_name != "ollama":
        raise click.ClickException("neste PR só --planner ollama (sem OpenRouter)")

    repo = _repo_root()
    root = _develop_root()
    try:
        plan = make_ollama_planner().plan(
            pedido, repo_root=repo, base_commit=_base_commit(repo)
        )
    except PlanValidationError as exc:
        raise click.ClickException(str(exc)) from exc
    path = save_plan(plan, root=root)
    click.echo(f"plano {plan.id} gravado em {path} ({len(plan.layers)} camada(s))")
    for layer in plan.layers:
        deps = ",".join(layer.depends_on) or "-"
        click.echo(f"  {layer.id} [{layer.status}] deps={deps}")


@develop_cli.command("export")
@click.argument("plan_id")
@click.option("--layer", "layer_id", required=True)
def develop_export(plan_id: str, layer_id: str) -> None:
    load_dotenv(override=False)
    from src.develop.export_md import export_layer
    from src.develop.store import load_plan

    root = _develop_root()
    plan = load_plan(plan_id, root=root)
    path = export_layer(plan, layer_id, root=root)
    click.echo(str(path))


@develop_cli.command("send")
@click.argument("plan_id")
@click.option("--layer", "layer_id", required=True)
@click.option("--dry-run", is_flag=True, default=False)
def develop_send(plan_id: str, layer_id: str, dry_run: bool) -> None:
    load_dotenv(override=False)
    from src.develop.cursor_send import preview_send, send_layer
    from src.develop.store import load_plan

    root = _develop_root()
    repo = _repo_root()
    plan = load_plan(plan_id, root=root)
    preview = preview_send(plan, layer_id, repo_root=repo)
    click.echo(f"pacote chars={len(preview.markdown)}")
    click.echo(f"destino bin={preview.binary!r}")
    click.echo(f"branch={preview.branch}")
    click.echo(f"worktree={preview.worktree}")
    if preview.blocked:
        raise click.ClickException(preview.blocked)
    if dry_run:
        click.echo(f"argv={preview.argv!r}")
        click.echo("dry-run: zero subprocess")
        return
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise click.ClickException("send real exige TTY")

    def confirm_fn(msg: str) -> bool:
        click.echo(msg)
        return click.confirm("Confirma envio", default=False)

    ok, message = send_layer(
        plan,
        layer_id,
        repo_root=repo,
        root=root,
        dry_run=False,
        confirm=True,
        confirm_fn=confirm_fn,
    )
    if not ok:
        raise click.ClickException(message)
    click.echo(message)
    click.echo("Lembrete: exit 0 do Cursor ≠ camada aceita. Use accept/reject.")


@develop_cli.command("accept")
@click.argument("plan_id")
@click.option("--layer", "layer_id", required=True)
def develop_accept(plan_id: str, layer_id: str) -> None:
    load_dotenv(override=False)
    from src.develop.store import load_plan, set_layer_status

    root = _develop_root()
    plan = load_plan(plan_id, root=root)
    layer = plan.layer(layer_id)
    if layer is None:
        raise click.ClickException(f"camada inexistente: {layer_id}")
    set_layer_status(plan, layer_id, "aceita", root=root)
    click.echo(f"{layer_id} → aceita")


@develop_cli.command("reject")
@click.argument("plan_id")
@click.option("--layer", "layer_id", required=True)
def develop_reject(plan_id: str, layer_id: str) -> None:
    load_dotenv(override=False)
    from src.develop.store import load_plan, set_layer_status

    root = _develop_root()
    plan = load_plan(plan_id, root=root)
    layer = plan.layer(layer_id)
    if layer is None:
        raise click.ClickException(f"camada inexistente: {layer_id}")
    set_layer_status(plan, layer_id, "rejeitada", root=root)
    click.echo(f"{layer_id} → rejeitada (dependentes continuam bloqueados)")


@develop_cli.command("show")
@click.argument("plan_id")
def develop_show(plan_id: str) -> None:
    load_dotenv(override=False)
    from src.develop.store import load_plan

    root = _develop_root()
    plan = load_plan(plan_id, root=root)
    click.echo(f"{plan.id} base={plan.base_commit} updated={plan.updated_at}")
    for layer in plan.layers:
        click.echo(
            f"  {layer.id} [{layer.status}] deps={layer.depends_on or []} "
            f"files={len(layer.allowed_files)}"
        )
