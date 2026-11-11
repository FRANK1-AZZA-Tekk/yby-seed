"""Keepalive enxuto do hub: checa Ollama e registra o estado.

Uso:
    python -m src.platform.hub
    python yby.py hub
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import Any

import requests
from dotenv import load_dotenv

DEFAULT_INTERVAL_SECONDS = 60.0
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT_SECONDS = 5.0

logger = logging.getLogger("yby.hub")


def check_ollama(base_url: str, *, timeout: float, session: Any | None = None) -> str:
    """Devolve 'ok' ou uma mensagem de erro curta."""

    url = f"{base_url.rstrip('/')}/api/tags"
    client = session or requests
    try:
        response = client.get(url, timeout=timeout)
    except requests.RequestException as exc:
        return f"indisponível ({exc})"
    if response.status_code >= 400:
        return f"HTTP {response.status_code}"
    return "ok"


def run_loop(
    *,
    base_url: str,
    interval: float,
    timeout: float,
    max_ticks: int | None = None,
) -> int:
    """Loop de saúde. `max_ticks` limita iterações (útil em testes)."""

    tick = 0
    logger.info("YBY hub ativo; Ollama=%s; intervalo=%ss", base_url, interval)
    while max_ticks is None or tick < max_ticks:
        status = check_ollama(base_url, timeout=timeout)
        logger.info("ollama=%s", status)
        tick += 1
        if max_ticks is not None and tick >= max_ticks:
            break
        time.sleep(interval)
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=False)
    parser = argparse.ArgumentParser(description="YBY hub keepalive")
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.environ.get("YBY_HUB_INTERVAL", DEFAULT_INTERVAL_SECONDS)),
        help="Segundos entre checagens",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Uma checagem e sai",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    base_url = os.environ.get("YBY_OLLAMA_BASE_URL", "").strip() or DEFAULT_OLLAMA_BASE_URL
    timeout = float(os.environ.get("YBY_HUB_TIMEOUT", DEFAULT_TIMEOUT_SECONDS))
    max_ticks = 1 if args.once else None
    return run_loop(
        base_url=base_url,
        interval=max(args.interval, 1.0),
        timeout=max(timeout, 0.1),
        max_ticks=max_ticks,
    )


if __name__ == "__main__":
    sys.exit(main())
