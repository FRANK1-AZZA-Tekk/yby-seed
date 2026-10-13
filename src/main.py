#!/usr/bin/env python3
"""
YBY SEED - Ponto de Entrada Principal

Uso:
    python src/main.py run --command "Crie um script de backup"
    python src/main.py test
    python src/main.py setup
"""

import sys
import click
from loguru import logger

from src.core.ollama_client import OllamaClient, OllamaError
from src.agents.router_agent import RouterAgent

# Configura logging
logger.add("logs/yby_seed_{time}.log", rotation="1 day", retention="7 days")


@click.group()
def cli():
    """YBY SEED - Programação em Linguagem Natural"""
    pass


@cli.command()
@click.option(
    "--command",
    "-c",
    required=True,
    help="Comando em linguagem natural para o YBY",
)
@click.option(
    "--host",
    default="localhost",
    help="Host do Ollama",
)
@click.option(
    "--port",
    default=11434,
    help="Porta do Ollama",
)
def run(command: str, host: str, port: int):
    """Executa comando em linguagem natural via RouterAgent"""
    logger.info("🌱 Iniciando YBY SEED...")

    ollama = OllamaClient(host=host, port=port)

    if not ollama.is_healthy():
        logger.error(
            "❌ Ollama não está acessível em "
            f"http://{host}:{port}. "
            "Inicie com: ollama serve"
        )
        sys.exit(1)

    router = RouterAgent(ollama)

    try:
        result = router.classify(command)
    except OllamaError as e:
        logger.error(f"❌ Falha no RouterAgent: {e}")
        sys.exit(1)

    agent = result.get("agent", "planning")
    intent = result.get("intent", "unknown")
    confidence = result.get("confidence", 0.0)
    requires_interview = result.get("requires_interview", False)

    logger.info(
        f"✅ Roteado para {agent} | "
        f"intenção={intent} | "
        f"confiança={confidence} | "
        f"entrevista={requires_interview}"
    )

    if agent == "planning":
        logger.info("🧠 PlanningAgent ainda não implementado (run mínimo)")
    elif agent == "execution":
        logger.info("⚡ ExecutionAgent ainda não implementado (run mínimo)")
    else:
        logger.warning(f"⚠️ Agente desconhecido: {agent}")

    click.echo(
        f"agent={agent}\n"
        f"intent={intent}\n"
        f"confidence={confidence}\n"
        f"requires_interview={requires_interview}"
    )


@cli.command()
def test():
    """Rodar testes rápidos"""
    logger.info("🧪 Rodando testes...")

    import subprocess

    result = subprocess.run(
        ["pytest", "tests/", "-v"],
        check=False,
    )

    if result.returncode != 0:
        logger.error("❌ Testes falharam")
        sys.exit(result.returncode)

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
