"""Cache particionado por sensibilidade e estado de saúde dos nós (Redis ou memória)."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Protocol, runtime_checkable

from src.yby.routing.schemas import RouteTier, Sensitivity


def build_cache_key(
    sensitivity: Sensitivity,
    tier: RouteTier,
    prompt: str,
    *,
    system_prompt: str | None = None,
) -> str:
    """Chave determinística particionada para evitar colisão entre private/public e system_prompt."""

    normalized = " ".join(prompt.strip().split())
    norm_sys = " ".join(system_prompt.strip().split()) if system_prompt else ""
    payload = f"{normalized}\x00sys:{norm_sys}" if norm_sys else normalized
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"yby:route:{sensitivity}:{tier}:{digest}"


@runtime_checkable
class CacheBackend(Protocol):
    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, *, ttl_seconds: int = 300) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def ping(self) -> bool: ...


class InMemoryCacheBackend:
    """Cache em memória com TTL monotônico e limite de entradas (evita vazamento de RAM)."""

    def __init__(self, *, clock: Any = None, max_entries: int = 2048) -> None:
        self._clock = clock or time.monotonic
        self._max_entries = max(1, int(max_entries))
        self._store: dict[str, tuple[str, float]] = {}

    def _prune_expired(self, now: float) -> None:
        expired = [k for k, (_, exp) in self._store.items() if now >= exp]
        for k in expired:
            self._store.pop(k, None)

    async def get(self, key: str) -> str | None:
        item = self._store.get(key)
        if item is None:
            return None
        value, expires_at = item
        if self._clock() >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: str, *, ttl_seconds: int = 300) -> None:
        ttl = max(1, int(ttl_seconds))
        now = self._clock()
        if key not in self._store and len(self._store) >= self._max_entries:
            self._prune_expired(now)
            while len(self._store) >= self._max_entries:
                oldest_key = next(iter(self._store))
                self._store.pop(oldest_key, None)
        self._store[key] = (value, now + ttl)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def ping(self) -> bool:
        return True


class RedisCacheBackend:
    """Adaptador assíncrono sobre `redis.asyncio` com import preguiçoso."""

    def __init__(self, url: str = "redis://127.0.0.1:6379/0", *, client: Any = None) -> None:
        self.url = url
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:
            raise RuntimeError(
                "Dependência opcional 'redis' não instalada. "
                "Instale com `uv sync --extra mesh` ou `pip install -r requirements-mesh.txt`."
            ) from exc
        self._client = aioredis.from_url(self.url, decode_responses=True)
        return self._client

    async def get(self, key: str) -> str | None:
        value = await self._get_client().get(key)
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

    async def set(self, key: str, value: str, *, ttl_seconds: int = 300) -> None:
        ttl = max(1, int(ttl_seconds))
        await self._get_client().set(key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        await self._get_client().delete(key)

    async def ping(self) -> bool:
        try:
            return bool(await self._get_client().ping())
        except Exception:  # noqa: BLE001
            return False


class NodeHealthTracker:
    """Circuit-breaker leve para nós da malha (ex.: PC Hub em manutenção -> Xiaomi 12)."""

    def __init__(
        self,
        cache: CacheBackend,
        *,
        unhealthy_ttl_seconds: int = 60,
    ) -> None:
        self._cache = cache
        self._unhealthy_ttl_seconds = max(1, unhealthy_ttl_seconds)

    @staticmethod
    def _key(node: str) -> str:
        return f"yby:health:unhealthy:{node}"

    async def mark_unhealthy(self, node: str, reason: str = "unreachable") -> None:
        await self._cache.set(self._key(node), reason, ttl_seconds=self._unhealthy_ttl_seconds)

    async def mark_healthy(self, node: str) -> None:
        await self._cache.delete(self._key(node))

    async def is_healthy(self, node: str) -> bool:
        return (await self._cache.get(self._key(node))) is None
