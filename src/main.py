#!/usr/bin/env python3
"""YBY SEED — ponto de entrada local-first.

Princípio: nenhum comando reporta sucesso sem executar uma ação verificável.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import click
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
REQUIRED_MODULES = ("click", "loguru", "pydantic", "pytest")
REQUIRED_PATHS = (
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "tests",
    PROJECT_ROOT / "requirements.txt",
)


def configure_logging() -> None:
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    logger.add(
        logs_dir / "yby_seed_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO",
        backtrace=True,
        diagnose=False,
    )


def python_executable() -> str:
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


@click.group()
def cli() -> None:
    """YBY SEED — hub local-first para automações e IA."""
    configure_logging()


@cli.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """Diagnostica Python, dependências e estrutura do repositório."""
    problems: list[str] = []

    if sys.version_info < (3, 11):
        problems.append(
            f"Python 3.11+ necessário (atual: {'.'.join(map(str, sys.version_info[:3]))})"
        )
    else:
        click.echo(f"OK Python {sys.version_info.major}.{sys.version_info.minor}")

    missing_mods = [
        name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None
    ]
    if missing_mods:
        problems.append("Dependências ausentes: " + ", ".join(missing_mods))
    else:
        click.echo("OK dependências básicas")

    missing_paths = [str(path) for path in REQUIRED_PATHS if not path.exists()]
    if missing_paths:
        problems.append("Estrutura incompleta: " + ", ".join(missing_paths))
    else:
        click.echo("OK estrutura do projeto")

    ollama = shutil.which("ollama")
    if ollama:
        click.echo(f"OK ollama no PATH ({ollama})")
        try:
            from src.core.ollama_client import OllamaClient

            client = OllamaClient()
            if client.is_healthy():
                models = client.list_models()
                click.echo(f"OK Ollama API ({len(models)} modelo(s))")
            else:
                click.echo("AVISO Ollama no PATH mas API não responde em :11434")
            client.close()
        except Exception as exc:  # noqa: BLE001
            click.echo(f"AVISO falha ao consultar Ollama API: {exc}")
    else:
        click.echo("AVISO ollama não encontrado no PATH (opcional no MVP)")

    if problems:
        for problem in problems:
            click.echo(f"ERRO {problem}", err=True)
        ctx.exit(1)

    click.echo("Doctor OK")


@cli.command()
@click.pass_context
def setup(ctx: click.Context) -> None:
    """Instala dependências Python no ambiente atual (sem Docker)."""
    requirements = PROJECT_ROOT / "requirements.txt"
    requirements_dev = PROJECT_ROOT / "requirements-dev.txt"
    py = python_executable()

    try:
        subprocess.run(
            [py, "-m", "pip", "install", "--upgrade", "pip"],
            check=True,
            cwd=PROJECT_ROOT,
        )
        subprocess.run(
            [py, "-m", "pip", "install", "-r", str(requirements)],
            check=True,
            cwd=PROJECT_ROOT,
        )
        if requirements_dev.exists():
            subprocess.run(
                [py, "-m", "pip", "install", "-r", str(requirements_dev)],
                check=True,
                cwd=PROJECT_ROOT,
            )
    except subprocess.CalledProcessError as exc:
        click.echo(f"Setup falhou (exit {exc.returncode})", err=True)
        ctx.exit(exc.returncode or 1)

    click.echo("Setup OK — dependências instaladas")
    click.echo("Próximo: python src/main.py doctor && python src/main.py test")


@cli.command()
@click.pass_context
def test(ctx: click.Context) -> None:
    """Executa a suíte de testes com pytest e propaga o código de saída."""
    py = python_executable()
    cmd = [
        py,
        "-m",
        "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--ignore=tests/test_gateway.py",
        "--ignore=tests/test_rag.py",
    ]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        click.echo(f"Testes falharam (exit {result.returncode})", err=True)
        ctx.exit(result.returncode)
    click.echo("Testes OK")


@cli.command()
@click.pass_context
def run(ctx: click.Context) -> None:
    """Núcleo interativo ainda não implementado no MVP."""
    click.echo(
        "Comando 'run' ainda não inicia o hub completo.\n"
        "Estado real: use 'doctor' e 'test'. "
        "O fluxo briefing/ask está no roadmap (Fase 1).\n"
        "Docker Compose atual sobe apenas Qdrant (pós-MVP).",
        err=True,
    )
    ctx.exit(2)


@cli.command()
def status() -> None:
    """Mostra o estado declarado do projeto sem iniciar serviços."""
    click.echo("Fase atual: 0 — consolidação / recuperação")
    click.echo("Implementado: doctor, setup, test, status")
    click.echo("Não implementado: run (hub completo), Node-RED, MQTT")
    click.echo("docker-compose.yml: apenas Qdrant (Fase 5+)")


if __name__ == "__main__":
    cli()
