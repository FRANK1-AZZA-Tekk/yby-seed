#!/usr/bin/env python3
"""YBY SEED — Ponto de entrada local-first.

Comandos:
    doctor   Diagnostica Python, dependências, estrutura e Ollama.
    setup    Prepara o ambiente local sem Docker.
    test     Executa a suíte de testes com pytest.
    run      Inicia o núcleo local do YBY SEED.

Princípio:
    Nenhum comando deve reportar sucesso sem executar uma ação real
    e verificável.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import click
import httpx
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_BIN = PROJECT_ROOT / ".venv" / "bin"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_TIMEOUT_SECONDS = 2.0

REQUIRED_MODULES: tuple[str, ...] = (
    "click",
    "httpx",
    "loguru",
    "pydantic",
)

REQUIRED_PATHS: tuple[Path, ...] = (
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "tests",
    PROJECT_ROOT / "requirements.txt",
)


def configure_logging() -> None:
    """Configura logs locais com rotação diária."""
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


def check_python() -> None:
    """Garante uma versão mínima suportada de Python."""
    if sys.version_info < (3, 11):
        current = ".".join(map(str, sys.version_info[:3]))
        raise RuntimeError(
            f"Python 3.11 ou superior é necessário. Versão atual: {current}."
        )


def check_dependencies() -> list[str]:
    """Valida módulos obrigatórios e retorna os módulos encontrados."""
    found: list[str] = []
    missing: list[str] = []

    for module_name in REQUIRED_MODULES:
        if importlib.util.find_spec(module_name) is None:
            missing.append(module_name)
        else:
            found.append(module_name)

    if missing:
        raise RuntimeError(
            "Dependências ausentes: "
            + ", ".join(missing)
            + ". Execute: pip install -r requirements.txt"
        )

    return found


def check_project_structure() -> None:
    """Valida se o repositório possui os diretórios e arquivos essenciais."""
    missing = [
        str(path)
        for path in REQUIRED_PATHS
        if not path.exists()
    ]

    if missing:
        raise RuntimeError(
            "Estrutura do projeto incompleta: " + ", ".join(missing)
        )


def check_ollama(timeout: float = OLLAMA_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Verifica se o Ollama está acessível e retorna os modelos locais."""
    url = f"{OLLAMA_URL}/api/tags"

    try:
        response = httpx.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Ollama não está acessível em {OLLAMA_URL}. "
            "Instale e inicie o Ollama antes de continuar."
        ) from exc
    except ValueError as exc:
        raise RuntimeError(
            "Ollama respondeu, mas retornou um payload inválido."
        ) from exc

    models = payload.get("models", [])

    if not isinstance(models, list):
        raise RuntimeError(
            "Ollama retornou uma lista de modelos inválida."
        )

    return {
        "available": True,
        "url": OLLAMA_URL,
        "models": models,
    }


def resolve_pytest() -> Path:
    """Localiza o executável pytest no venv ou no PATH."""
    venv_pytest = VENV_BIN / "pytest"

    if venv_pytest.exists():
        return venv_pytest

    system_pytest = shutil.which("pytest")

    if system_pytest:
        return Path(system_pytest)

    raise RuntimeError(
        "pytest não encontrado. "
        "Execute: make install-dev ou pip install -r requirements-dev.txt"
    )


@click.group()
def cli() -> None:
    """YBY SEED — Programação em linguagem natural, local-first."""


@cli.command()
def doctor() -> None:
    """Diagnostica o ambiente local do YBY SEED."""
    configure_logging()

    try:
        check_python()
        logger.success("✅ Python compatível.")

        dependencies = check_dependencies()
        logger.success(
            f"✅ Dependências encontradas: {', '.join(dependencies)}."
        )

        check_project_structure()
        logger.success("✅ Estrutura do projeto válida.")

        ollama = check_ollama()
        model_count = len(ollama["models"])
        logger.success(
            f"✅ Ollama acessível em {ollama['url']} "
            f"com {model_count} modelo(s)."
        )

        logger.success("🌱 Ambiente YBY SEED pronto para uso local.")

    except RuntimeError as exc:
        logger.error(f"❌ Diagnóstico falhou: {exc}")
        raise SystemExit(1) from exc


@cli.command()
def setup() -> None:
    """Prepara e valida o ambiente local, sem Docker."""
    configure_logging()

    try:
        logger.info("🛠️ Preparando ambiente YBY SEED...")

        check_python()
        logger.success("✅ Python compatível.")

        check_project_structure()
        logger.success("✅ Estrutura do projeto válida.")

        logger.info("📦 Validando dependências...")
        check_dependencies()
        logger.success("✅ Dependências Python encontradas.")

        logger.info("🧠 Verificando Ollama...")
        ollama = check_ollama()
        logger.success(
            f"✅ Ollama acessível com {len(ollama['models'])} modelo(s)."
        )

        logger.success("✅ Ambiente local pronto.")
        logger.info("Próximo passo: python src/main.py run")

    except RuntimeError as exc:
        logger.error(f"❌ Setup falhou: {exc}")
        raise SystemExit(1) from exc


@cli.command()
def test() -> None:
    """Executa a suíte de testes com pytest."""
    configure_logging()

    try:
        pytest_path = resolve_pytest()
    except RuntimeError as exc:
        logger.error(f"❌ {exc}")
        raise SystemExit(1) from exc

    logger.info("🧪 Executando testes...")

    result = subprocess.run(
        [
            str(pytest_path),
            "tests/",
            "-v",
            "--tb=short",
        ],
        cwd=PROJECT_ROOT,
        check=False,
    )

    if result.returncode != 0:
        logger.error(
            f"❌ Testes falharam com código de saída {result.returncode}."
        )
        raise SystemExit(result.returncode)

    logger.success("✅ Testes concluídos com sucesso.")


@cli.command()
def run() -> None:
    """Inicia o núcleo local do YBY SEED."""
    configure_logging()

    try:
        logger.info("🌱 Iniciando YBY SEED...")

        check_python()
        check_dependencies()
        check_project_structure()

        logger.info("🧠 Verificando Ollama...")
        ollama = check_ollama()

        models = ollama["models"]
        model_names = [
            model.get("name", "modelo sem nome")
            for model in models
        ]

        logger.success(
            f"✅ Ollama acessível em {ollama['url']}."
        )
        logger.info(
            "Modelos detectados: "
            + (", ".join(model_names) if model_names else "nenhum")
        )

        # Ponto de integração do MVP.
        #
        # Próxima etapa planejada:
        # 1. Carregar o RouterAgent.
        # 2. Receber um pedido em linguagem natural.
        # 3. Conduzir entrevista mínima.
        # 4. Gerar briefing/PRD estruturado.
        # 5. Permitir revisão e aprovação do usuário.
        # 6. Exportar Markdown e JSON.
        #
        # Importante: esta Camada 1 não executa código gerado,
        # não acessa serviços externos e não inicia Docker.

        logger.warning(
            "⚠️ O pipeline conversacional ainda não está integrado. "
            "O núcleo está em modo de inicialização e diagnóstico."
        )

        logger.success(
            "✅ YBY SEED inicializado em modo local-first."
        )

    except RuntimeError as exc:
        logger.error(f"❌ Falha ao iniciar o YBY SEED: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    cli()
