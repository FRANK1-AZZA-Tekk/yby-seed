"""Singletons de runtime (HTTP, PostgreSQL, Docker) — ciclo de vida via FastAPI lifespan."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx

from src.yby_seed.config import Settings, get_settings

if TYPE_CHECKING:
    from openai import OpenAI
    from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

_http_client: httpx.Client | None = None
_pg_pool: AsyncConnectionPool | None = None
_docker_client: Any = None


def database_url(settings: Settings | None = None) -> str:
    import os

    settings = settings or get_settings()
    dsn = os.environ.get("YBY_DATABASE_URL", "").strip()
    if dsn:
        return dsn
    password = os.environ.get("POSTGRES_PASSWORD", "yby_local_dev")
    return f"postgresql://yby:{password}@127.0.0.1:5432/yby_brain"


def get_http_client() -> httpx.Client:
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _http_client


def build_openai_client(settings: Settings | None = None) -> OpenAI:
    from openai import OpenAI

    settings = settings or get_settings()
    return OpenAI(
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
        http_client=get_http_client(),
    )


async def open_pg_pool(settings: Settings | None = None) -> AsyncConnectionPool | None:
    global _pg_pool
    from psycopg_pool import AsyncConnectionPool

    if _pg_pool is not None:
        return _pg_pool
    dsn = database_url(settings)
    try:
        pool = AsyncConnectionPool(conninfo=dsn, min_size=0, max_size=4, open=False)
        await pool.open()
        _pg_pool = pool
        logger.info("pool PostgreSQL ativo")
        return pool
    except Exception as exc:  # noqa: BLE001
        logger.warning("pool PostgreSQL indisponível: %s", exc)
        return None


def get_pg_pool() -> AsyncConnectionPool | None:
    return _pg_pool


def get_docker_client_sync() -> Any:
    """Cliente Docker SDK (síncrono); usar via asyncio.to_thread no sandbox."""
    global _docker_client
    if _docker_client is not None:
        return _docker_client
    import docker

    _docker_client = docker.from_env()
    return _docker_client


async def startup(settings: Settings | None = None) -> None:
    get_http_client()
    await open_pg_pool(settings)


async def shutdown() -> None:
    global _http_client, _pg_pool, _docker_client
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
    if _http_client is not None:
        _http_client.close()
        _http_client = None
    if _docker_client is not None:
        try:
            _docker_client.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("fechamento docker client: %s", exc)
        _docker_client = None
