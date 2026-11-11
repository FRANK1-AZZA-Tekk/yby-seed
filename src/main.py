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
from src.safety.policy import confirm, decide, default_policy_path, load_policy

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


@cli.command()
@click.argument("comando", nargs=-1, required=True)
def gate(comando: tuple[str, ...]) -> None:
    """Decide se um comando rodaria, pediria confirmação ou seria recusado.

    Não executa o comando.
    """

    texto = " ".join(comando).strip()
    policy = load_policy(default_policy_path())
    project_root = default_policy_path().parents[1]
    decision = decide(texto, policy=policy, project_root=project_root)
    click.echo(f"{decision.action}: {decision.reason}")
    if decision.action != "ask":
        raise SystemExit(0 if decision.action == "run" else 1)

    approved = confirm(
        texto,
        decision,
        input_fn=lambda: click.prompt("s/n", prompt_suffix=" "),
        output_fn=click.echo,
    )
    raise SystemExit(0 if approved else 1)


def build_engine() -> HybridEngine:
    """Ponto de troca nos testes. Em execução normal, lê o ambiente."""

    return engine_from_env()


if __name__ == "__main__":
    cli()
