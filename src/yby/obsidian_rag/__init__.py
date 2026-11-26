"""Indexador leve Obsidian Markdown -> RAG híbrido (`pgvector` com fallback offline)."""

from __future__ import annotations

from src.yby.obsidian_rag.indexer import (
    AsyncTextEmbedder,
    ObsidianVaultIndexer,
    ReindexReport,
)
from src.yby.obsidian_rag.parser import (
    ObsidianChunk,
    ParsedObsidianNote,
    chunk_obsidian_document,
    parse_obsidian_markdown,
)
from src.yby.obsidian_rag.store import (
    HybridSearchHit,
    InMemoryObsidianStore,
    ObsidianChunkStore,
    PgVectorObsidianStore,
    create_obsidian_store_from_env,
)

__all__ = [
    "AsyncTextEmbedder",
    "HybridSearchHit",
    "InMemoryObsidianStore",
    "ObsidianChunk",
    "ObsidianChunkStore",
    "ObsidianVaultIndexer",
    "ParsedObsidianNote",
    "PgVectorObsidianStore",
    "ReindexReport",
    "chunk_obsidian_document",
    "create_obsidian_store_from_env",
    "parse_obsidian_markdown",
]
