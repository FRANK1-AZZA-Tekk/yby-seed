"""Pipeline do YBY Machine: reuse -> cache -> translate -> fallback -> persist -> compile."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from src.yby_machine.cache import AsyncSpecFingerprintCache
from src.yby_machine.compiler import compile_pwa
from src.yby_machine.embedder import OfflineHashEmbedder
from src.yby_machine.ports import (
    AppSummary,
    EmbedderPort,
    SpecStorePort,
    StoredAppRecord,
    TranslateCachePort,
)
from src.yby_machine.spec import YBYSpec
from src.yby_machine.store import DEFAULT_REUSE_THRESHOLD, InMemorySpecStore
from src.yby_machine.translator import TranslateResult, prompt_to_spec_result

PipelineSource = Literal["reuse", "cache", "ollama", "litellm", "fallback"]
TranslatorFn = Callable[[str], Awaitable[TranslateResult]]


@dataclass(frozen=True)
class PipelineResult:
    """Saída do pipeline com origem explícita, app_id persistido e bundle PWA."""

    app_id: str
    spec: YBYSpec
    files: dict[str, str]
    source: PipelineSource
    created_at: str
    similarity: float | None = None


async def _default_translator(prompt: str) -> TranslateResult:
    return await prompt_to_spec_result(prompt, cache=None)


class MachinePipeline:
    """Orquestra reuso semântico, cache de tradução, tradutor e compilação PWA."""

    def __init__(
        self,
        *,
        embedder: EmbedderPort | None = None,
        store: SpecStorePort | None = None,
        cache: TranslateCachePort | None = None,
        translator: TranslatorFn | None = None,
        min_similarity: float = DEFAULT_REUSE_THRESHOLD,
    ) -> None:
        self.embedder: EmbedderPort = embedder or OfflineHashEmbedder()
        self.store: SpecStorePort = store or InMemorySpecStore()
        self.cache: TranslateCachePort = cache or AsyncSpecFingerprintCache()
        self._translator: TranslatorFn = translator or _default_translator
        self.min_similarity = min_similarity

    async def generate(self, prompt: str) -> PipelineResult:
        text = (prompt or "").strip()
        embedding = await self.embedder.embed(text)

        # 1) Gate de reuso semântico (similaridade cosseno >= 0.92)
        reused = await self.store.find_similar(
            embedding,
            min_similarity=self.min_similarity,
        )
        if reused is not None:
            return PipelineResult(
                app_id=reused.app_id,
                spec=reused.spec,
                files=compile_pwa(reused.spec),
                source="reuse",
                created_at=reused.created_at,
                similarity=reused.similarity,
            )

        # 2) Cache de tradução por fingerprint
        cached = await self.cache.get(text)
        if cached is not None:
            record = await self.store.save(
                prompt=text,
                embedding=embedding,
                spec=cached.spec,
                source="cache",
            )
            return PipelineResult(
                app_id=record.app_id,
                spec=cached.spec,
                files=compile_pwa(cached.spec),
                source="cache",
                created_at=record.created_at,
            )

        # 3) Tradutor (Ollama local por padrão, LiteLLM só via env, ou fallback)
        translated = await self._translator(text)
        await self.cache.put(text, translated)

        record = await self.store.save(
            prompt=text,
            embedding=embedding,
            spec=translated.spec,
            source=translated.source,
        )
        return PipelineResult(
            app_id=record.app_id,
            spec=translated.spec,
            files=compile_pwa(translated.spec),
            source=translated.source,
            created_at=record.created_at,
        )

    async def list_apps(self, *, limit: int = 50) -> list[AppSummary]:
        return await self.store.list_apps(limit=limit)

    async def get_app(self, app_id: str) -> tuple[StoredAppRecord, dict[str, str]] | None:
        record = await self.store.get_app(app_id)
        if record is None:
            return None
        return record, compile_pwa(record.spec)

    async def close(self) -> None:
        await self.embedder.close()
        await self.store.close()
        await self.cache.close()
