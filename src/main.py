#!/usr/bin/env python3
"""
YBY SEED - Ponto de Entrada Principal (MVP Fase 1)

Uso:
    python src/main.py

Comandos:
    health   - Verifica saude do ambiente (Ollama, data/)
    ask      - Envia um pedido ao Ollama local
"""

import os
import click
from loguru import logger
from src.core.ollama_client import OllamaClient
from src.core.gatekeeper import match_command

logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DEFAULT_MODEL = os.environ.get("YBY_MODEL", "qwen3:4b")
OLLAMA_HOST = os.environ.get("YBY_OLLAMA_HOST", "localhost")
OLLAMA_PORT = int(os.environ.get("YBY_OLLAMA_PORT", "11434"))


@click.group()
def cli():
    """YBY SEED - Nucleo local-first (MVP Fase 1)"""


@cli.command()
def health():
    """Verifica saude do ambiente (Ollama, data/)"""
    client = OllamaClient(host=OLLAMA_HOST, port=OLLAMA_PORT)
    ollama_ok = client.is_healthy()
    data_ok = os.path.isdir(DATA_DIR)

    click.echo(f"Ollama ({OLLAMA_HOST}:{OLLAMA_PORT}): {'OK' if ollama_ok else 'FALHA'}")
    click.echo(f"Diretorio data/: {'OK' if data_ok else 'AUSENTE'}")

    if ollama_ok:
        models = client.list_models()
        click.echo(f"Modelos disponiveis: {len(models)}")
        if DEFAULT_MODEL in models:
            click.echo(f"Modelo padrao '{DEFAULT_MODEL}': OK")
        else:
            click.echo(f"Modelo padrao '{DEFAULT_MODEL}': NAO ENCONTRADO")

    if not (ollama_ok and data_ok):
        raise SystemExit(1)

    click.echo("Ambiente saudavel.")


@cli.command()
@click.argument("text")
def ask(text: str):
    """Envia um pedido ao Ollama local"""
    command = match_command(text)

    if command == "parar":
        click.echo("Solicitação encerrada.")
        raise SystemExit(0)

    if command is not None:
        click.echo(
            "ERRO: comando reconhecido, mas a funcionalidade "
            "ainda não está implementada. Nenhuma alteração foi aplicada.",
            err=True,
        )
        raise SystemExit(5)

    client = OllamaClient(host=OLLAMA_HOST, port=OLLAMA_PORT)

    if not client.is_healthy():
        click.echo("ERRO: Ollama nao esta respondendo.", err=True)
        raise SystemExit(2)

    models = client.list_models()
    if DEFAULT_MODEL not in models:
        click.echo(
            f"ERRO: modelo '{DEFAULT_MODEL}' nao encontrado. "
            f"Execute: ollama pull {DEFAULT_MODEL}",
            err=True,
        )
        raise SystemExit(3)

    logger.info(f"Enviando pedido ao modelo {DEFAULT_MODEL}...")
    response = client.generate(
        model=DEFAULT_MODEL,
        prompt=text,
        options={"num_ctx": 4096, "temperature": 0.6},
    )

    if not response:
        click.echo("ERRO: resposta vazia do Ollama.", err=True)
        raise SystemExit(4)

    click.echo(response)


if __name__ == "__main__":
    cli()
