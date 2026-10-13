#!/usr/bin/env python3
"""
YBY SEED - Ponto de Entrada Principal

Uso:
    python src/main.py

Comandos:
    run     - Inicia o sistema
    test    - Roda testes rápidos
    setup   - Configura ambiente
"""

import sys
import click
from loguru import logger

# Configura logging
logger.add("logs/yby_seed_{time}.log", rotation="1 day", retention="7 days")


@click.group()
def cli():
    """YBY SEED - Programação em Linguagem Natural"""
    pass


@cli.command()
def run():
    """Inicia o sistema YBY SEED"""
    logger.error("❌ Comando 'run' ainda não está implementado.")
    logger.info("📌 Estado atual: Fase 0 — Consolidação; nenhum serviço completo é iniciado por este comando.")
    raise click.exceptions.Exit(code=1)


@cli.command()
def test():
    """Rodar testes rápidos"""
    logger.error("❌ Comando 'test' ainda não está implementado.")
    logger.info("📌 Use 'make test' para executar a suíte pytest atual.")
    raise click.exceptions.Exit(code=1)


@cli.command()
def setup():
    """Configurar ambiente"""
    logger.error("❌ Comando 'setup' ainda não está implementado.")
    logger.info("📌 Use 'make setup' para criar o ambiente virtual e instalar dependências.")
    raise click.exceptions.Exit(code=1)


if __name__ == "__main__":
    cli()
