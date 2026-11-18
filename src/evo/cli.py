"""Click subcommands: `yby evo ...` / `python -m src.evo`."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import click

from src.evo.collect import ingest_cloud_log, ingest_dicts, seed_demo_events
from src.evo.paths import resolve_db_path, resolve_reports_dir
from src.evo.pipeline import _USE_DEFAULT_COMPLETER, generate_report, open_store


def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@click.group("evo")
def evo_cli() -> None:
    """Evo v0.1 — observabilidade local (relatórios apenas; offline)."""


@evo_cli.command("report")
@click.option(
    "--day",
    default=None,
    help="Dia UTC YYYY-MM-DD (padrão: hoje UTC).",
)
@click.option(
    "--db",
    type=click.Path(path_type=Path),
    default=None,
    help="Caminho do SQLite (padrão: $XDG_DATA_HOME/yby/evo/evo.sqlite3).",
)
@click.option(
    "--out",
    "reports_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Pasta de relatórios (padrão: evo/reports/).",
)
@click.option(
    "--seed-demo",
    is_flag=True,
    help="Injeta eventos simulados para o dia (útil para smoke).",
)
@click.option(
    "--no-cloud-log",
    is_flag=True,
    help="Não lê logs/cloud_usage.jsonl.",
)
@click.option(
    "--no-ollama",
    is_flag=True,
    help="Força análise heurística (sem chamar Ollama).",
)
@click.option("--stdout", "to_stdout", is_flag=True, help="Também imprime o Markdown.")
def report_cmd(
    day: str | None,
    db: Path | None,
    reports_dir: Path | None,
    seed_demo: bool,
    no_cloud_log: bool,
    no_ollama: bool,
    to_stdout: bool,
) -> None:
    """Agrega o dia, analisa (Ollama local ou heurística) e escreve Markdown."""

    target = day or today_utc()
    completer: object = None if no_ollama else _USE_DEFAULT_COMPLETER

    bundle = generate_report(
        target,
        db_path=db,
        reports_dir=reports_dir,
        completer=completer,
        seed_demo=seed_demo,
        ingest_cloud=not no_cloud_log,
    )
    click.echo(f"report: {bundle.path}")
    click.echo(f"db: {bundle.db_path}")
    click.echo(f"events: {bundle.aggregate.total}")
    click.echo(f"cycle: {bundle.cycle_state}")
    if to_stdout:
        click.echo(bundle.markdown)


@evo_cli.command("ingest")
@click.option(
    "--day",
    default=None,
    help="Dia dos eventos demo (com --seed-demo).",
)
@click.option(
    "--db",
    type=click.Path(path_type=Path),
    default=None,
)
@click.option("--seed-demo", is_flag=True, help="Insere o pacote de eventos simulados.")
@click.option(
    "--cloud-log/--no-cloud-log",
    default=True,
    help="Importar JSONL local de uso de nuvem se existir.",
)
def ingest_cmd(
    day: str | None,
    db: Path | None,
    seed_demo: bool,
    cloud_log: bool,
) -> None:
    """Só coleta/persiste eventos (sanitizados). Não gera relatório."""

    target = day or today_utc()
    path = resolve_db_path(db)
    with open_store(path) as store:
        n = 0
        if seed_demo:
            n += ingest_dicts(store, seed_demo_events(target))
        if cloud_log:
            n += ingest_cloud_log(store)
    click.echo(f"ingested≈{n} into {path}")
    click.echo(f"reports dir (unused here): {resolve_reports_dir()}")


@evo_cli.command("search")
@click.argument("query")
@click.option("--day", default=None)
@click.option("--db", type=click.Path(path_type=Path), default=None)
@click.option("--limit", default=20, show_default=True, type=int)
def search_cmd(query: str, day: str | None, db: Path | None, limit: int) -> None:
    """Busca FTS5 nos eventos sanitizados."""

    with open_store(resolve_db_path(db)) as store:
        hits = store.search(query, day=day, limit=limit)
    if not hits:
        click.echo("Nenhum evento.")
        return
    for hit in hits:
        click.echo(f"{hit['day']} {hit['kind']}: {hit['summary']}")
