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

import click
from loguru import logger

from src.engine.hybrid import HybridEngine, engine_from_env

# Configura logging
logger.add("logs/yby_seed_{time}.log", rotation="1 day", retention="7 days")


@click.group()
def cli():
    """YBY SEED - Programação em Linguagem Natural"""
    pass


@cli.command()
def run():
    """Inicia o sistema YBY SEED"""
    logger.info("🌱 Iniciando YBY SEED...")
    
    # TODO: Implementar inicialização completa
    # 1. Carrega modelos Ollama
    # 2. Inicia Node-RED flows
    # 3. Conecta ao MQTT broker
    # 4. Inicia TUI (Textual)
    
    logger.info("✅ YBY SEED iniciado com sucesso!")
    logger.info("📌 Acesse http://localhost:1880 (Node-RED)")


@cli.command()
def test():
    """Rodar testes rápidos"""
    logger.info("🧪 Rodando testes...")
    
    # TODO: Implementar suite de testes
    # pytest tests/ -v
    
    logger.info("✅ Testes concluídos!")


@cli.command()
def setup():
    """Configurar ambiente"""
    logger.info("🛠️  Configurando ambiente...")
    
    # TODO: Implementar setup automático
    # 1. Cria ambiente virtual
    # 2. Instala dependências
    # 3. Baixa modelos Ollama
    # 4. Configura Docker
    
    logger.info("✅ Ambiente configurado!")


@cli.command()
@click.option(
    "--heavy",
    is_flag=True,
    help="Força a nuvem, mesmo num pedido curto.",
)
@click.argument("pergunta", nargs=-1, required=True)
def ask(heavy: bool, pergunta: tuple[str, ...]) -> None:
    """Responde um pedido em texto. Sem voz, shell ou memória."""

    texto = " ".join(pergunta).strip()
    if not texto:
        click.echo('Informe um pedido. Exemplo: yby ask "explica uma lista"', err=True)
        raise SystemExit(1)

    resposta = build_engine().reply(texto, explicit_heavy=heavy)
    if resposta.notice:
        click.echo(resposta.notice, err=True)
    if resposta.provider == "none":
        raise SystemExit(1)

    motivo = "; ".join(resposta.reasons)
    click.echo(f"modelo: {resposta.provider} {resposta.model} ({motivo})", err=True)
    click.echo(resposta.text)


def build_engine() -> HybridEngine:
    """Ponto de troca nos testes. Em execução normal, lê o ambiente."""

    return engine_from_env()


if __name__ == "__main__":
    cli()
