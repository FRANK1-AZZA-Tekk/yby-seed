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
from src.agents.planning_agent import PlanningAgent
from src.agents.execution_agent import ExecutionAgent
from src.agents.validation_agent import ValidationAgent
from src.rag.rag_optimizer import RAGOptimizer

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
@click.option(
    "--rag",
    is_flag=True,
    default=False,
    help="Usar RAG para enriquecer contexto",
)
def run(command: str, host: str, port: int, rag: bool):
    """Executa comando em linguagem natural via fluxo completo"""
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

    agent = result.agent
    intent = result.intent
    confidence = result.confidence
    requires_interview = result.requires_interview

    logger.info(
        f"✅ Roteado para {agent} | "
        f"intenção={intent} | "
        f"confiança={confidence} | "
        f"entrevista={requires_interview}"
    )

    validator = ValidationAgent()

    if agent == "planning":
        planner = PlanningAgent(ollama)
        try:
            prd = planner.interview(command, mode="junior")
        except OllamaError as e:
            logger.error(f"❌ Falha no PlanningAgent: {e}")
            sys.exit(1)

        executor = ExecutionAgent(ollama)

        try:
            if rag:
                rag_optimizer = RAGOptimizer(ollama)
                rag_chunks = rag_optimizer.retrieve(command)
                logger.info(f"📚 RAG: {len(rag_chunks)} chunks recuperados")
                generated = executor.generate_with_rag(
                    prd.model_dump_json(), rag_chunks
                )
            else:
                generated = executor.generate(prd.model_dump_json())
        except OllamaError as e:
            logger.error(f"❌ Falha no ExecutionAgent: {e}")
            sys.exit(1)

        # Validação do código gerado
        is_valid, errors = validator.validate(generated.code)

        if not is_valid:
            logger.error(f"❌ Código gerado falhou na validação: {errors}")
            suggestions = validator.suggest_fixes(generated.code, errors)
            logger.info(f"💡 Sugestões: {suggestions}")
            sys.exit(1)

        logger.info("✅ Código validado com sucesso")

        click.echo("\n--- PRD ---\n")
        click.echo(prd.model_dump_json(indent=2))
        click.echo("\n--- CÓDIGO ---\n")
        click.echo(generated.code)

    elif agent == "execution":
        executor = ExecutionAgent(ollama)

        try:
            if rag:
                rag_optimizer = RAGOptimizer(ollama)
                rag_chunks = rag_optimizer.retrieve(command)
                logger.info(f"📚 RAG: {len(rag_chunks)} chunks recuperados")
                generated = executor.generate_with_rag(
                    f"Responda diretamente à pergunta: {command}",
                    rag_chunks,
                )
            else:
                generated = executor.generate(
                    f"Responda diretamente à pergunta: {command}"
                )
        except OllamaError as e:
            logger.error(f"❌ Falha no ExecutionAgent: {e}")
            sys.exit(1)

        # Validação do código gerado
        is_valid, errors = validator.validate(generated.code)

        if not is_valid:
            logger.error(f"❌ Código gerado falhou na validação: {errors}")
            suggestions = validator.suggest_fixes(generated.code, errors)
            logger.info(f"💡 Sugestões: {suggestions}")
            sys.exit(1)

        logger.info("✅ Código validado com sucesso")

        click.echo("\n--- RESPOSTA ---\n")
        click.echo(generated.code)

    else:
        logger.warning(f"⚠️ Agente desconhecido: {agent}")
        sys.exit(1)


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
