"""Cache de YBYSpec por fingerprint do prompt (memória por padrão; Redis opcional lazy)."""

from __future__ import annotations

import inspect
import json
import os
from collections import OrderedDict
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from src.yby_machine.ports import TranslateCachePort
from src.yby_machine.spec import YBYSpec

if TYPE_CHECKING:
    from src.yby_machine.translator import TranslateResult


def prompt_fingerprint(prompt: str) -> str:
    """Hash estável do prompt (casefold + strip) para reuso local."""

    import hashlib

    normalized = (prompt or "").strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class SpecFingerprintCache:
    """LRU síncrono em memória (mantido por compatibilidade com callers existentes)."""

    def __init__(self, max_size: int = 64) -> None:
        if max_size < 1:
            raise ValueError("max_size deve ser >= 1")
        self._max_size = max_size
        self._store: OrderedDict[str, TranslateResult] = OrderedDict()

    def get(self, prompt: str) -> TranslateResult | None:
        key = prompt_fingerprint(prompt)
        hit = self._store.get(key)
        if hit is None:
            return None
        self._store.move_to_end(key)
        return hit

    def put(self, prompt: str, result: TranslateResult) -> None:
        key = prompt_fingerprint(prompt)
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = result
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)


class AsyncSpecFingerprintCache:
    """Adapter assíncrono em memória implementando `TranslateCachePort`."""

    def __init__(
        self,
        max_size: int = 64,
        *,
        inner: SpecFingerprintCache | None = None,
    ) -> None:
        self._inner = inner or SpecFingerprintCache(max_size=max_size)

    async def get(self, prompt: str) -> TranslateResult | None:
        return self._inner.get(prompt)

    async def put(self, prompt: str, result: TranslateResult) -> None:
        self._inner.put(prompt, result)

    async def close(self) -> None:
        return None


class RedisTranslateCache:
    """Cache opcional via Redis (`redis.asyncio` lazy); degrada para memória em erro."""

    def __init__(
        self,
        redis_url: str,
        *,
        ttl_seconds: int = 3600,
        key_prefix: str = "yby:machine:spec:",
        client: Any | None = None,
        fallback: AsyncSpecFingerprintCache | None = None,
    ) -> None:
        self.redis_url = redis_url
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.key_prefix = key_prefix
        self._client = client
        self._owns_client = client is None
        self._fallback = fallback or AsyncSpecFingerprintCache()

    def _get_client(self) -> Any:
        if self._client is None:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._client

    def _redis_key(self, prompt: str) -> str:
        return f"{self.key_prefix}{prompt_fingerprint(prompt)}"

    async def get(self, prompt: str) -> TranslateResult | None:
        from src.yby_machine.translator import TranslateResult

        try:
            client = self._get_client()
            raw = await client.get(self._redis_key(prompt))
            if not raw:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            payload = json.loads(raw)
            spec = YBYSpec.model_validate(payload["spec"])
            source = payload.get("source", "fallback")
            if source not in ("ollama", "litellm", "fallback"):
                source = "fallback"
            return TranslateResult(spec=spec, source=source)
        except Exception:  # noqa: BLE001
            return await self._fallback.get(prompt)

    async def put(self, prompt: str, result: TranslateResult) -> None:
        encoded = json.dumps(
            {"spec": result.spec.model_dump(mode="json"), "source": result.source},
            ensure_ascii=False,
        )
        try:
            client = self._get_client()
            await client.set(self._redis_key(prompt), encoded, ex=self.ttl_seconds)
        except Exception:  # noqa: BLE001
            await self._fallback.put(prompt, result)

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            closer = getattr(self._client, "aclose", None) or getattr(self._client, "close", None)
            if closer is not None:
                res = closer()
                if inspect.isawaitable(res):
                    await res
        await self._fallback.close()


def create_translate_cache_from_env(
    environ: Mapping[str, str] | None = None,
) -> TranslateCachePort:
    """Ativa RedisTranslateCache só com YBY_REDIS_URL + `redis.asyncio` importável."""

    source = environ if environ is not None else os.environ
    redis_url = source.get("YBY_REDIS_URL", "").strip()
    if not redis_url:
        return AsyncSpecFingerprintCache()
    try:
        import redis.asyncio  # noqa: F401
    except ImportError:
        return AsyncSpecFingerprintCache()
    return RedisTranslateCache(redis_url=redis_url)


DEFAULT_SPEC_CACHE = SpecFingerprintCache()
