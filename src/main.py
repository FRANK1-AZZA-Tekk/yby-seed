#!/usr/bin/env python3
"""
YBY SEED - Ponto de Entrada Principal (MVP Fase 1)

Uso:
    python src/main.py

Comandos:
    health   - Verifica saude do ambiente (Ollama, data/, modelo padrao)
    ask      - Envia um pedido ao Ollama local

Codigos de saida:
    0 sucesso | 1 ambiente nao saudavel | 2 Ollama indisponivel
    3 modelo ausente | 4 resposta vazia | 5 comando nao implementado
    6 operacao bloqueada pela politica de transporte
    7 falha tecnica do cliente Ollama
"""

import os
from contextlib import nullcontext

import click
from loguru import logger
from src.core.audit import audit_context
from src.core.ollama_client import (
    OllamaClient,
    OllamaClientError,
    OllamaPolicyError,
)
from src.core.gatekeeper import match_command
from src.core.router import RunPolicy, route_request

logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DEFAULT_MODEL = os.environ.get("YBY_MODEL", "qwen3:4b")
OLLAMA_HOST = os.environ.get("YBY_OLLAMA_HOST", "localhost")
OLLAMA_PORT = os.environ.get("YBY_OLLAMA_PORT", "11434")


def _make_ollama_client() -> OllamaClient:
    try:
        port = int(OLLAMA_PORT)
    except (TypeError, ValueError):
        raise OllamaPolicyError(
            "Porta do Ollama não permitida pela política local."
        ) from None

    return OllamaClient(host=OLLAMA_HOST, port=port)


@click.group()
def cli():
    """YBY SEED - Nucleo local-first (MVP Fase 1)"""


@cli.command()
def health():
    """Verifica saude do ambiente (Ollama, data/, modelo padrao)"""
    try:
        client = _make_ollama_client()
        ollama_ok = client.is_healthy()
    except OllamaPolicyError as exc:
        click.echo(f"ERRO: {exc}", err=True)
        raise SystemExit(1) from None

    data_ok = os.path.isdir(DATA_DIR)
    model_ok = False

    click.echo(f"Ollama ({OLLAMA_HOST}:{OLLAMA_PORT}): {'OK' if ollama_ok else 'FALHA'}")
    click.echo(f"Diretorio data/: {'OK' if data_ok else 'AUSENTE'}")

    if ollama_ok:
        try:
            models = client.list_models()
        except OllamaPolicyError as exc:
            click.echo(f"ERRO: {exc}", err=True)
            raise SystemExit(1) from None
        except OllamaClientError as exc:
            click.echo(f"ERRO: {exc}", err=True)
            raise SystemExit(1) from None

        click.echo(f"Modelos disponiveis: {len(models)}")
        model_ok = DEFAULT_MODEL in models
        if model_ok:
            click.echo(f"Modelo padrao '{DEFAULT_MODEL}': OK")
        else:
            click.echo(f"Modelo padrao '{DEFAULT_MODEL}': NAO ENCONTRADO")

    if not (ollama_ok and data_ok and model_ok):
        raise SystemExit(1)

    click.echo("Ambiente saudavel.")


@cli.command()
@click.argument("text")
@click.option(
    "--offline",
    is_flag=True,
    default=False,
    help="Executa sem qualquer rota de nuvem (no MVP nenhuma rota de nuvem existe).",
)
@click.option(
    "--private",
    is_flag=True,
    default=False,
    help="Nao persiste auditoria desta interacao.",
)
@click.option(
    "--audit",
    is_flag=True,
    default=False,
    help="Grava metadados de auditoria (nunca prompt ou resposta).",
)
def ask(text: str, offline: bool, private: bool, audit: bool):
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

    policy = RunPolicy(offline=offline, private=private)
    decision = route_request(policy)

    if decision.route != "local_ollama":
        click.echo(
            "ERRO: rota não implementada. Nenhuma alteração foi aplicada.",
            err=True,
        )
        raise SystemExit(5)

    if audit and private:
        click.echo(
            "AVISO: --private prevalece; auditoria não será gravada.",
            err=True,
        )

    audit_enabled = audit and not private
    audit_cm = audit_context(DEFAULT_MODEL) if audit_enabled else nullcontext()

    with audit_cm as recorder:
        try:
            client = _make_ollama_client()
            ollama_ok = client.is_healthy()
        except OllamaPolicyError as exc:
            if recorder:
                recorder.finish("error", 6)
            click.echo(f"ERRO: {exc}", err=True)
            raise SystemExit(6) from None

        if not ollama_ok:
            if recorder:
                recorder.finish("error", 2)
            click.echo("ERRO: Ollama nao esta respondendo.", err=True)
            raise SystemExit(2)

        try:
            models = client.list_models()
        except OllamaPolicyError as exc:
            if recorder:
                recorder.finish("error", 6)
            click.echo(f"ERRO: {exc}", err=True)
            raise SystemExit(6) from None
        except OllamaClientError as exc:
            if recorder:
                recorder.finish("error", 7)
            click.echo(f"ERRO: {exc}", err=True)
            raise SystemExit(7) from None

        if DEFAULT_MODEL not in models:
            if recorder:
                recorder.finish("error", 3)
            click.echo(
                f"ERRO: modelo '{DEFAULT_MODEL}' nao encontrado. "
                f"Execute: ollama pull {DEFAULT_MODEL}",
                err=True,
            )
            raise SystemExit(3)

        logger.info(f"Enviando pedido ao modelo {DEFAULT_MODEL}...")
        try:
            response = client.generate(
                model=DEFAULT_MODEL,
                prompt=text,
                options={"num_ctx": 4096, "temperature": 0.6},
            )
        except OllamaPolicyError as exc:
            if recorder:
                recorder.finish("error", 6)
            click.echo(f"ERRO: {exc}", err=True)
            raise SystemExit(6) from None
        except OllamaClientError as exc:
            if recorder:
                recorder.finish("error", 7)
            click.echo(f"ERRO: {exc}", err=True)
            raise SystemExit(7) from None

        if not response:
            if recorder:
                recorder.finish("empty", 4)
            click.echo("ERRO: resposta vazia do Ollama.", err=True)
            raise SystemExit(4)

        if recorder:
            recorder.finish("ok", 0)
        click.echo(response)


if __name__ == "__main__":
    cli()
