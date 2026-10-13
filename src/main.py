#!/usr/bin/env python3
"""YBY SEED - Ponto de Entrada Principal."""

import importlib.util
import platform
import shutil
import subprocess
import sys

import click
from loguru import logger

from src.core.graph import ask


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
def ask(question: tuple[str, ...]):
    """Faz uma pergunta mínima ao núcleo YBY."""
    text = " ".join(question).strip()
    if not text:
        raise click.exceptions.Exit(code=1)
    try:
        click.echo(ask(text))
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
