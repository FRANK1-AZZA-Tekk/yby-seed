"""Consulta ao índice Chroma (somente chunks; sem documentos inteiros)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.schema import NodeWithScore
from llama_index.core.vector_stores import FilterOperator, MetadataFilter, MetadataFilters
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

import chromadb

from src.yby.rag.ingest import (
    DEFAULT_CHROMA_DIR,
    DEFAULT_COLLECTION_NAME,
    DEFAULT_EMBED_MODEL,
)

DEFAULT_TOP_K = 5
DEFAULT_MAX_CONTEXT_CHARS = 4000
_FETCH_OVERSAMPLE = 4


@dataclass(frozen=True)
class RetrieveHit:
    text: str
    score: float
    source: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RetrieveResult:
    query: str
    hits: list[RetrieveHit]
    context_text: str
    context_chars: int
    max_context_chars: int
    truncated: bool
    metadata: dict[str, Any] = field(default_factory=dict)


class RagRetriever:
    """Recupera chunks do índice vetorial existente."""

    def __init__(
        self,
        *,
        chroma_dir: Path | None = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        embed_model: BaseEmbedding | None = None,
        ollama_base_url: str | None = None,
        embed_model_name: str = DEFAULT_EMBED_MODEL,
    ) -> None:
        self.chroma_dir = (chroma_dir or DEFAULT_CHROMA_DIR).resolve()
        self.collection_name = collection_name

        base_url = ollama_base_url or os.getenv("YBY_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self._embed_model = embed_model or OllamaEmbedding(
            model_name=embed_model_name,
            base_url=base_url,
        )
        Settings.embed_model = self._embed_model

        self._client = chromadb.PersistentClient(path=str(self.chroma_dir))
        self._collection = self._client.get_or_create_collection(self.collection_name)
        vector_store = ChromaVectorStore(chroma_collection=self._collection)
        self._index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

    def search(
        self,
        query: str,
        *,
        top_k: int = DEFAULT_TOP_K,
        doc_type: str | None = None,
        tags: list[str] | None = None,
        access_level: str | None = None,
        max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    ) -> RetrieveResult:
        if not query.strip():
            raise ValueError("query não pode ser vazia")
        if top_k < 1:
            raise ValueError("top_k deve ser >= 1")
        if max_context_chars < 1:
            raise ValueError("max_context_chars deve ser >= 1")

        metadata_filters = _build_metadata_filters(
            doc_type=doc_type,
            access_level=access_level,
        )
        fetch_k = top_k * _FETCH_OVERSAMPLE if tags else top_k

        retriever = self._index.as_retriever(
            similarity_top_k=fetch_k,
            filters=metadata_filters,
        )
        nodes = retriever.retrieve(query.strip())

        if tags:
            nodes = [node for node in nodes if _tags_match(node.node.metadata.get("tags"), tags)]

        nodes = nodes[:top_k]
        hits = [_node_to_hit(node) for node in nodes]
        context_text, truncated, used = _build_context(hits, max_context_chars)

        return RetrieveResult(
            query=query.strip(),
            hits=hits,
            context_text=context_text,
            context_chars=used,
            max_context_chars=max_context_chars,
            truncated=truncated,
            metadata={
                "top_k": top_k,
                "filters": {
                    "doc_type": doc_type,
                    "tags": tags or [],
                    "access_level": access_level,
                },
                "chunk_count": len(hits),
            },
        )


def search_knowledge(
    query: str,
    *,
    chroma_dir: Path | None = None,
    top_k: int = DEFAULT_TOP_K,
    doc_type: str | None = None,
    tags: list[str] | None = None,
    access_level: str | None = None,
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    embed_model: BaseEmbedding | None = None,
) -> RetrieveResult:
    retriever = RagRetriever(chroma_dir=chroma_dir, embed_model=embed_model)
    return retriever.search(
        query,
        top_k=top_k,
        doc_type=doc_type,
        tags=tags,
        access_level=access_level,
        max_context_chars=max_context_chars,
    )


def _build_metadata_filters(
    *,
    doc_type: str | None,
    access_level: str | None,
) -> MetadataFilters | None:
    filters: list[MetadataFilter] = []
    if doc_type:
        filters.append(
            MetadataFilter(key="doc_type", operator=FilterOperator.EQ, value=doc_type)
        )
    if access_level:
        filters.append(
            MetadataFilter(
                key="access_level",
                operator=FilterOperator.EQ,
                value=access_level,
            )
        )
    if not filters:
        return None
    return MetadataFilters(filters=filters)


def _parse_tags(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return [part.strip() for part in raw.split(",") if part.strip()]
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return []


def _tags_match(raw: Any, required: list[str]) -> bool:
    if not required:
        return True
    present = {tag.lower() for tag in _parse_tags(raw)}
    needed = {tag.lower() for tag in required}
    return needed.issubset(present)


def _node_to_hit(node: NodeWithScore) -> RetrieveHit:
    meta = dict(node.node.metadata or {})
    text = node.node.get_content(metadata_mode="none")
    source = str(meta.get("source", ""))
    score = float(node.score if node.score is not None else 0.0)
    return RetrieveHit(text=text, score=score, source=source, metadata=meta)


def _build_context(
    hits: list[RetrieveHit],
    max_context_chars: int,
) -> tuple[str, bool, int]:
    """Monta contexto só com trechos de chunk; nunca lê arquivo fonte do disco."""

    parts: list[str] = []
    total = 0
    truncated = False

    for hit in hits:
        snippet = hit.text.strip()
        if not snippet:
            continue
        header = f"[{hit.source}#{hit.metadata.get('chunk_index', '?')}]"
        block = f"{header}\n{snippet}"

        if total + len(block) + 2 > max_context_chars:
            remaining = max_context_chars - total - 2
            if remaining > len(header) + 2:
                block = block[:remaining]
                parts.append(block)
                total = max_context_chars
            truncated = True
            break

        parts.append(block)
        total += len(block) + 2

    return "\n\n".join(parts), truncated, min(total, max_context_chars)