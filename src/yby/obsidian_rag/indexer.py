"""Indexador incremental de notas Markdown do cofre Obsidian para RAG híbrido (pgvector)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from src.yby.obsidian_rag.parser import (
    ObsidianChunk,
    chunk_obsidian_document,
    parse_obsidian_markdown,
)
from src.yby.obsidian_rag.store import (
    HybridSearchHit,
    InMemoryObsidianStore,
    ObsidianChunkStore,
)
from src.yby_machine.embedder import OfflineHashEmbedder

_IGNORED_DIRS = frozenset({".obsidian", ".yby", ".git", ".trash", "node_modules"})


@runtime_checkable
class AsyncTextEmbedder(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class ReindexReport(BaseModel):
    """Resumo determinístico de uma execução de reindexação incremental."""

    model_config = ConfigDict(extra="forbid")

    vault_path: str
    backend: str
    files_scanned: int
    files_indexed: int
    files_skipped: int
    files_removed: int
    chunks_upserted: int
    total_chunks: int


def _should_skip(path: Path, root: Path) -> bool:
    rel_parts = path.resolve().relative_to(root.resolve()).parts
    return any(part in _IGNORED_DIRS for part in rel_parts)


def _embedding_input(chunk: ObsidianChunk) -> str:
    meta_bits: list[str] = []
    if chunk.heading:
        meta_bits.append(chunk.heading)
    if chunk.wikilinks:
        meta_bits.append(" ".join(chunk.wikilinks))
    if chunk.tags:
        meta_bits.append(" ".join(chunk.tags))
    prefix = " | ".join(meta_bits)
    return f"{prefix}\n{chunk.content}" if prefix else chunk.content


class ObsidianVaultIndexer:
    """Lê arquivos `.md` do cofre, extrai YAML + wikilinks e indexa chunks incrementalmente."""

    def __init__(
        self,
        *,
        store: ObsidianChunkStore | None = None,
        embedder: AsyncTextEmbedder | None = None,
        max_chars: int = 900,
        overlap: int = 120,
    ) -> None:
        self.store: ObsidianChunkStore = store or InMemoryObsidianStore()
        self.embedder: AsyncTextEmbedder = embedder or OfflineHashEmbedder()
        self.max_chars = max_chars
        self.overlap = overlap
        self._file_hashes: dict[str, str] = {}
        self._schema_ready = False

    async def _ensure_ready(self) -> None:
        if not self._schema_ready:
            await self.store.ensure_schema()
            self._schema_ready = True

    async def reindex_vault(
        self,
        vault_path: Path | str,
        *,
        force: bool = False,
    ) -> ReindexReport:
        """Reindexa apenas notas `.md` novas/modificadas (ou todas se `force=True`)."""

        await self._ensure_ready()
        root = Path(vault_path).resolve()
        if not root.exists():
            total = await self.store.count_chunks()
            return ReindexReport(
                vault_path=str(root),
                backend=self.store.backend_name,
                files_scanned=0,
                files_indexed=0,
                files_skipped=0,
                files_removed=0,
                chunks_upserted=0,
                total_chunks=total,
            )

        files_scanned = 0
        files_indexed = 0
        files_skipped = 0
        chunks_upserted = 0
        seen_paths: set[str] = set()

        for md_path in sorted(root.rglob("*.md")):
            if not md_path.is_file() or _should_skip(md_path, root):
                continue
            rel_path = md_path.resolve().relative_to(root).as_posix()
            seen_paths.add(rel_path)
            files_scanned += 1

            raw_text = md_path.read_text(encoding="utf-8")
            digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            if not force and self._file_hashes.get(rel_path) == digest:
                files_skipped += 1
                continue

            parsed = parse_obsidian_markdown(raw_text, source_path=rel_path)
            chunks = chunk_obsidian_document(
                parsed,
                max_chars=self.max_chars,
                overlap=self.overlap,
            )
            await self.store.delete_by_source(rel_path)
            if chunks:
                embeddings = [await self.embedder.embed(_embedding_input(c)) for c in chunks]
                chunks_upserted += await self.store.upsert_chunks(chunks, embeddings)
            self._file_hashes[rel_path] = digest
            files_indexed += 1

        files_removed = 0
        for stale_path in [path for path in list(self._file_hashes) if path not in seen_paths]:
            await self.store.delete_by_source(stale_path)
            del self._file_hashes[stale_path]
            files_removed += 1

        total_chunks = await self.store.count_chunks()
        return ReindexReport(
            vault_path=str(root),
            backend=self.store.backend_name,
            files_scanned=files_scanned,
            files_indexed=files_indexed,
            files_skipped=files_skipped,
            files_removed=files_removed,
            chunks_upserted=chunks_upserted,
            total_chunks=total_chunks,
        )

    async def search(
        self,
        query: str,
        *,
        limit: int = 5,
        wikilink: str | None = None,
        tag: str | None = None,
    ) -> list[HybridSearchHit]:
        """Executa busca semântica híbrida (vetor + texto + filtros de metadados)."""

        await self._ensure_ready()
        query_vec = await self.embedder.embed(query)
        return await self.store.hybrid_search(
            query,
            query_vec,
            limit=limit,
            wikilink=wikilink,
            tag=tag,
        )
