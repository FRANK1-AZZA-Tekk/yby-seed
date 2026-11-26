"""Embedder padrão offline (hash/n-gram) + adapter opcional Ollama por env."""

from __future__ import annotations

import asyncio
import hashlib
import math
import os
import re
import unicodedata
from collections.abc import Mapping

from src.engine.config import DEFAULT_OLLAMA_BASE_URL

DEFAULT_EMBEDDING_DIM = 128
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").strip().casefold())
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(without_accents.split())


def _hash_bucket(feature: str, dim: int) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    raw = int.from_bytes(digest, "little")
    idx = raw % dim
    sign = 1.0 if ((raw >> 63) & 1) == 0 else -1.0
    return idx, sign


class OfflineHashEmbedder:
    """Vetor determinístico offline (tokens + 3-gramas), sem rede nem deps extras."""

    def __init__(self, dim: int = DEFAULT_EMBEDDING_DIM) -> None:
        if dim < 8:
            raise ValueError("dim deve ser >= 8")
        self.dim = dim

    def embed_sync(self, text: str) -> list[float]:
        norm = _normalize_text(text)
        vec = [0.0] * self.dim
        if not norm:
            return vec

        tokens = _TOKEN_RE.findall(norm)
        for tok in tokens:
            idx, sign = _hash_bucket(f"w:{tok}", self.dim)
            vec[idx] += 2.0 * sign
            if len(tok) >= 3:
                padded = f"<{tok}>"
                for i in range(len(padded) - 2):
                    gram = padded[i : i + 3]
                    g_idx, g_sign = _hash_bucket(f"g:{gram}", self.dim)
                    vec[g_idx] += g_sign

        norm_val = math.sqrt(sum(v * v for v in vec))
        if norm_val == 0.0:
            return vec
        return [v / norm_val for v in vec]

    async def embed(self, text: str) -> list[float]:
        return self.embed_sync(text)

    async def close(self) -> None:
        return None


class OllamaEmbedder:
    """Adapter opcional via Ollama `/api/embeddings`; falha cai no offline."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        model: str = "all-minilm:22m",
        timeout: float = 10.0,
        fallback: OfflineHashEmbedder | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._fallback = fallback or OfflineHashEmbedder()

    def _call_ollama(self, text: str) -> list[float] | None:
        import requests

        resp = requests.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        emb = data.get("embedding")
        if isinstance(emb, list) and emb:
            return [float(x) for x in emb]
        return None

    async def embed(self, text: str) -> list[float]:
        try:
            vec = await asyncio.to_thread(self._call_ollama, text)
            if vec:
                return vec
        except Exception:  # noqa: BLE001
            pass
        return await self._fallback.embed(text)

    async def close(self) -> None:
        await self._fallback.close()


def create_embedder_from_env(
    environ: Mapping[str, str] | None = None,
) -> OfflineHashEmbedder | OllamaEmbedder:
    """Padrão offline; ativa Ollama embeddings só se YBY_MACHINE_EMBEDDER=ollama."""

    source = environ if environ is not None else os.environ
    mode = source.get("YBY_MACHINE_EMBEDDER", "offline").strip().casefold()
    if mode == "ollama":
        base = (
            source.get("YBY_OLLAMA_BASE_URL")
            or source.get("OLLAMA_API_BASE")
            or DEFAULT_OLLAMA_BASE_URL
        ).strip()
        model = source.get("OLLAMA_MODEL_EMBEDDING", "all-minilm:22m").strip() or "all-minilm:22m"
        return OllamaEmbedder(base_url=base, model=model)
    return OfflineHashEmbedder()
