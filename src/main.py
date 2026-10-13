#!/usr/bin/env python3
"""YBY SEED - Ponto de Entrada Principal."""

import importlib.util
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import click
from loguru import logger

from src.core.graph import ask as ask_graph
from src.core.memory import MemoryStore
from src.core.skills import list_skills, run_skill


def _port_open(host: str, port: int) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


@click.group()
def cli():
    """YBY SEED - Programação em Linguagem Natural"""
    pass


@cli.group()
def skills():
    """Gerencia skills locais do YBY."""


@skills.command("list")
def skills_list():
    """Lista as skills disponíveis."""
    for skill in list_skills():
        confirmation = " [requer confirmação]" if skill.requires_confirmation else ""
        click.echo(f"{skill.name}: {skill.description}{confirmation}")


@skills.command("run")
@click.argument("name")
@click.option("--arg", "args", multiple=True, help="Argumento no formato chave=valor.")
@click.option("--yes", is_flag=True, help="Confirma execução de skill que exige aprovação.")
def skills_run(name: str, args: tuple[str, ...], yes: bool):
    """Executa uma skill registrada."""
    parsed: dict[str, str] = {}
    for item in args:
        if "=" not in item:
            raise click.exceptions.Exit(code=1)
        key, value = item.split("=", 1)
        parsed[key] = value
    try:
        click.echo(run_skill(name, parsed, confirm=yes))
    except KeyError as exc:
        logger.error(str(exc))
        raise click.exceptions.Exit(code=1)
    except PermissionError as exc:
        logger.error(str(exc))
        raise click.exceptions.Exit(code=2)
    except Exception as exc:
        logger.error(f"Falha ao executar a skill: {exc}")
        raise click.exceptions.Exit(code=1)


@cli.command()
def status():
    """Mostra o estado local do ambiente YBY SEED."""
    click.echo("YBY SEED — status local")
    click.echo(f"Python: {platform.python_version()}")
    click.echo(f"pytest: {'disponível' if importlib.util.find_spec('pytest') else 'não encontrado'}")
    click.echo(f"Ollama: {'disponível' if shutil.which('ollama') else 'não encontrado (opcional)'}")
    click.echo(f"Docker: {'disponível' if shutil.which('docker') else 'não encontrado (opcional)'}")
    click.echo(f"Qdrant (127.0.0.1:6333): {'acessível' if _port_open('127.0.0.1', 6333) else 'indisponível (opcional)'}")
    click.echo("Nenhum serviço foi iniciado por este comando.")


@cli.command()
@click.argument("question", nargs=-1, required=True)
@click.option("--cite", is_flag=True, help="Usa documentos Markdown locais e inclui citações.")
@click.option("--remember", is_flag=True, help="Salva a interação na memória local.")
@click.option("--memory-dir", type=click.Path(path_type=Path), default=None, help="Diretório da memória local.")
def ask(question: tuple[str, ...], cite: bool, remember: bool, memory_dir: Path | None):
    """Faz uma pergunta ao núcleo YBY."""
    text = " ".join(question).strip()
    if not text:
        raise click.exceptions.Exit(code=1)
    memory = MemoryStore(memory_dir / "memory.jsonl") if memory_dir else None
    try:
        answer, citations = ask_graph(text, cite=cite, remember=remember, memory=memory)
        click.echo(answer)
        if citations:
            click.echo("\nFontes:")
            for citation in citations:
                click.echo(f"- {citation}")
    except Exception as exc:
        logger.error(f"Falha ao processar a pergunta: {exc}")
        raise click.exceptions.Exit(code=1)


@cli.command()
def run():
    """Inicia o sistema YBY SEED."""
    logger.error("Comando 'run' ainda não está implementado.")
    logger.info("Estado atual: Fase 0 — Consolidação; nenhum serviço completo é iniciado.")
    raise click.exceptions.Exit(code=1)


@cli.command()
def test():
    """Executa a suíte de testes com pytest."""
    logger.info("Executando pytest...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"])
    raise click.exceptions.Exit(code=result.returncode)


@cli.command()
def setup():
    """Configura o ambiente de desenvolvimento."""
    logger.error("Comando 'setup' ainda não está implementado.")
    logger.info("Use 'make setup' para criar o ambiente virtual e instalar dependências.")
    raise click.exceptions.Exit(code=1)


if __name__ == "__main__":
    cli()
