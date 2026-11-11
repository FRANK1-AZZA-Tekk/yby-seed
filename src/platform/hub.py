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
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

DEFAULT_INTERVAL_SECONDS = 60.0
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_KEEP_ALIVE = "30m"
DEFAULT_NUM_CTX = 4096
DEFAULT_LOCAL_MODEL = "qwen2.5-coder:3b"

logger = logging.getLogger("yby.hub")

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def is_loopback_ollama_url(base_url: str) -> bool:
    """True se o host for loopback (D9 / fase P: sem Ollama remoto)."""

    host = (urlparse(base_url).hostname or "").casefold()
    if not host:
        return False
    if host in _LOOPBACK_HOSTS or host.startswith("127."):
        return True
    return host == "::1"


def default_hub_log_path() -> Path:
    custom = os.environ.get("YBY_HUB_LOG", "").strip()
    if custom:
        return Path(custom).expanduser()
    return Path.home() / ".local" / "state" / "yby-seed" / "hub.log"


def setup_logging(*, log_path: Path | None = None) -> None:
    """stderr + arquivo local (sem nuvem, sem porta)."""

    path = log_path or default_hub_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    for handler in (
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(path, encoding="utf-8"),
    ):
        handler.setFormatter(fmt)
        root.addHandler(handler)


def default_local_model() -> str:
    return (
        os.environ.get("YBY_LOCAL_MODEL", "").strip()
        or os.environ.get("OLLAMA_DEFAULT_MODEL", "").strip()
        or DEFAULT_LOCAL_MODEL
    )


def ollama_ping_payload(
    *,
    model: str | None = None,
    keep_alive: str | None = None,
    num_ctx: int | None = None,
) -> dict[str, Any]:
    """Payload mínimo de generate para manter o modelo quente (loopback)."""

    return {
        "model": model or default_local_model(),
        "prompt": "",
        "stream": False,
        "keep_alive": (keep_alive or os.environ.get("OLLAMA_KEEP_ALIVE", DEFAULT_KEEP_ALIVE)).strip()
        or DEFAULT_KEEP_ALIVE,
        "options": {
            "num_ctx": num_ctx
            if num_ctx is not None
            else int(os.environ.get("YBY_OLLAMA_NUM_CTX", DEFAULT_NUM_CTX)),
        },
    }


def check_ollama(
    base_url: str,
    *,
    timeout: float,
    session: Any | None = None,
    model: str | None = None,
    keep_alive: str | None = None,
    num_ctx: int | None = None,
) -> str:
    """Devolve 'ok' ou uma mensagem de erro curta."""

    client = session or requests
    post = getattr(client, "post", None)
    if post is not None:
        url = f"{base_url.rstrip('/')}/api/generate"
        payload = ollama_ping_payload(model=model, keep_alive=keep_alive, num_ctx=num_ctx)
        try:
            response = post(url, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            return f"indisponível ({exc})"
        if response.status_code >= 400:
            return f"HTTP {response.status_code}"
        return "ok"

    url = f"{base_url.rstrip('/')}/api/tags"
    get = getattr(client, "get", None)
    if get is None:
        return "indisponível (cliente sem HTTP)"
    try:
        response = get(url, timeout=timeout)
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
    session: Any | None = None,
) -> int:
    """Loop de saúde. `max_ticks` limita iterações (útil em testes)."""

    if not is_loopback_ollama_url(base_url):
        logger.error("URL Ollama fora do loopback: %s", base_url)
        return 2

    tick = 0
    logger.info("YBY hub ativo; Ollama=%s; intervalo=%ss", base_url, interval)
    while max_ticks is None or tick < max_ticks:
        status = check_ollama(base_url, timeout=timeout, session=session)
        if status == "ok":
            logger.info("ollama=%s", status)
        else:
            logger.warning("ollama falhou: %s", status)
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

    setup_logging()

    base_url = os.environ.get("YBY_OLLAMA_BASE_URL", "").strip() or DEFAULT_OLLAMA_BASE_URL
    if not is_loopback_ollama_url(base_url):
        logger.error("YBY_OLLAMA_BASE_URL precisa ser loopback: %s", base_url)
        return 2

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
