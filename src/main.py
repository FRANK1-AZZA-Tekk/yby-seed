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


if __name__ == "__main__":
    cli()
