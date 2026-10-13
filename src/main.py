#!/usr/bin/env python3
"""YBY SEED — ponto de entrada principal.

Comandos:
    python -m src.main run      Inicia o núcleo mínimo local.
    python -m src.main serve    Inicia apenas a API FastAPI local.
    python -m src.main test     Executa a suíte de testes.
    python -m src.main doctor   Verifica ambiente e dependências.

Princípios:
- Local-first: Ollama é opcional, mas recomendado para inferência privada.
- Fail-closed: componentes não prontos não são simulados como prontos.
- Sem execução de código gerado nesta fase.
- Sem segredos no código; usar variáveis de ambiente.
"""

from __future__ import annotations

import importlib.util
import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
import uvicorn
from loguru import logger

# Garante importação de `src.*` quando executado como script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.ollama_client import OllamaClient  # noqa: E402

logger.remove()
logger.add(sys.stderr, level=os.getenv("YBY_LOG_LEVEL", "INFO"))
logger.add(
    "logs/yby_seed_{time}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
    enqueue=True,
)


@dataclass(frozen=True)
class Settings:
    """Configuração local, sem segredos embutidos."""

    host: str = os.getenv("YBY_HOST", "127.0.0.1")
    port: int = int(os.getenv("YBY_PORT", "8000"))
    ollama_host: str = os.getenv("YBY_OLLAMA_HOST", "127.0.0.1")
    ollama_port: int = int(os.getenv("YBY_OLLAMA_PORT", "11434"))
    mqtt_host: str = os.getenv("YBY_MQTT_HOST", "127.0.0.1")
    mqtt_port: int = int(os.getenv("YBY_MQTT_PORT", "1883"))
    log_level: str = os.getenv("YBY_LOG_LEVEL", "INFO")


SETTINGS = Settings()


def _module_available(module_name: str) -> bool:
    """Verifica se um módulo Python está importável."""

    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


def _tcp_open(host: str, port: int, timeout: float = 1.5) -> bool:
    """Testa conectividade TCP sem enviar dados sensíveis."""

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _check_python() -> dict[str, Any]:
    version = sys.version_info
    ok = version >= (3, 11)
    return {
        "name": "python",
        "ok": ok,
        "detail": f"{version.major}.{version.minor}.{version.micro}",
        "fix": "Use Python 3.11 ou superior." if not ok else "",
    }


def _check_dependencies() -> dict[str, Any]:
    required = ["click", "loguru", "fastapi", "uvicorn", "pydantic", "requests"]
    missing = [name for name in required if not _module_available(name)]
    return {
        "name": "dependencies",
        "ok": not missing,
        "detail": "todas presentes" if not missing else f"ausentes: {', '.join(missing)}",
        "fix": "Instale as dependências com `pip install -r requirements.txt`." if missing else "",
    }


def _check_ollama() -> dict[str, Any]:
    client = OllamaClient(host=SETTINGS.ollama_host, port=SETTINGS.ollama_port)
    healthy = client.is_healthy()
    models = client.list_models() if healthy else []
    return {
        "name": "ollama",
        "ok": healthy,
        "detail": (
            f"{len(models)} modelo(s) disponível(is)"
            if healthy
            else f"indisponível em {SETTINGS.ollama_host}:{SETTINGS.ollama_port}"
        ),
        "fix": "Inicie o Ollama e confirme o host/porta." if not healthy else "",
    }


def _check_mqtt() -> dict[str, Any]:
    reachable = _tcp_open(SETTINGS.mqtt_host, SETTINGS.mqtt_port)
    return {
        "name": "mqtt",
        "ok": reachable,
        "detail": (
            f"broker acessível em {SETTINGS.mqtt_host}:{SETTINGS.mqtt_port}"
            if reachable
            else f"broker não acessível em {SETTINGS.mqtt_host}:{SETTINGS.mqtt_port}"
        ),
        "fix": "Inicie um broker MQTT local ou ajuste YBY_MQTT_HOST/YBY_MQTT_PORT." if not reachable else "",
    }


def _check_openrouter_config() -> dict[str, Any]:
    key_present = bool(os.getenv("OPENROUTER_API_KEY"))
    return {
        "name": "openrouter",
        "ok": True,
        "detail": "chave configurada" if key_present else "chave não configurada; modo local apenas",
        "fix": "Configure OPENROUTER_API_KEY no ambiente seguro para habilitar nuvem." if not key_present else "",
    }


def _run_checks(include_optional: bool = True) -> list[dict[str, Any]]:
    checks = [_check_python(), _check_dependencies(), _check_ollama()]

    if include_optional:
        checks.append(_check_mqtt())
        checks.append(_check_openrouter_config())

    return checks


def _print_checks(checks: list[dict[str, Any]]) -> bool:
    all_required_ok = True

    for check in checks:
        symbol = "✅" if check["ok"] else "❌"
        logger.info(f"{symbol} {check['name']}: {check['detail']}")

        if check.get("fix"):
            logger.info(f"   ↳ {check['fix']}")

        # Ollama é necessário para o núcleo atual; MQTT/OpenRouter são opcionais.
        if check["name"] in {"python", "dependencies", "ollama"} and not check["ok"]:
            all_required_ok = False

    return all_required_ok


@click.group()
def cli() -> None:
    """YBY SEED — programação e automação em linguagem natural."""


@cli.command()
def doctor() -> None:
    """Verifica ambiente, dependências e serviços locais."""

    logger.info("🩺 Executando diagnóstico YBY SEED...")
    checks = _run_checks()
    required_ok = _print_checks(checks)

    if not required_ok:
        raise SystemExit(1)

    logger.info("✅ Núcleo pronto para iniciar.")


@cli.command()
def test() -> None:
    """Executa a suíte de testes automatizados."""

    if not _module_available("pytest"):
        logger.error("pytest não está instalado.")
        logger.info("Instale com: pip install -r tests/requirements.txt")
        raise SystemExit(1)

    import pytest

    logger.info("🧪 Executando testes...")
    exit_code = pytest.main(["tests", "-v"])
    raise SystemExit(exit_code)


@cli.command()
def serve() -> None:
    """Inicia apenas a API FastAPI local do gateway."""

    logger.info("🌐 Iniciando API YBY SEED...")
    logger.warning(
        "Prototype: persistência, MQTT ingestion e autenticação ainda não implementados. "
        "Use apenas em loopback/rede confiável."
    )

    uvicorn.run(
        "src.gateway.fastapi_mqtt_bridge:app",
        host=SETTINGS.host,
        port=SETTINGS.port,
        reload=False,
        log_level=SETTINGS.log_level.lower(),
    )


@cli.command()
def run() -> None:
    """Inicia o núcleo mínimo do YBY SEED."""

    logger.info("🌱 Iniciando YBY SEED...")

    checks = _run_checks()
    required_ok = _print_checks(checks)

    if not required_ok:
        logger.error("Núcleo não pode iniciar com segurança.")
        raise SystemExit(1)

    logger.info("🧠 Núcleo local pronto.")
    logger.info("🚫 Execução de código gerado permanece desabilitada.")
    logger.info("🌐 API disponível em http://{}:{}".format(SETTINGS.host, SETTINGS.port))
    logger.warning(
        "Prototype: persistência, MQTT ingestion e autenticação ainda não implementados."
    )

    uvicorn.run(
        "src.gateway.fastapi_mqtt_bridge:app",
        host=SETTINGS.host,
        port=SETTINGS.port,
        reload=False,
        log_level=SETTINGS.log_level.lower(),
    )


if __name__ == "__main__":
    cli()
