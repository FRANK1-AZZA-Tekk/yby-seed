#!/usr/bin/env python3
"""YBY SEED - Ponto de Entrada Principal."""

import subprocess
import sys

import click
from loguru import logger


@click.group()
def cli():
    """YBY SEED - Programação em Linguagem Natural"""
    pass


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
