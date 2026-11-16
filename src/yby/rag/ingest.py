"""Ingestão de documentos no Chroma (LlamaIndex + Ollama)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

import chromadb

from src.yby.rag.chunking import attach_chunk_positions, build_nodes
from src.yby.rag.config import RagConfig
from src.yby.rag.embedder import create_embedder
from src.yby.rag.errors import IngestionError, UnsupportedDocumentError
from src.yby.rag.loaders import (
    SUPPORTED_SUFFIXES,
    assert_knowledge_path,
    load_document,
    metadata_from_text as _metadata_from_text,
    sha256_file,
    tags_to_chroma as _tags_to_chroma,
)
from src.yby.rag.models import IngestionResult

logger = logging.getLogger("yby.rag.ingest")

MANIFEST_FILENAME = "ingest_manifest.json"

# Reexports de compatibilidade (T3+ e testes legados).
CHUNK_SIZE_TOKENS = 800
CHUNK_OVERLAP_TOKENS = 120
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_CHROMA_DIR = Path("data/chroma")
DEFAULT_COLLECTION_NAME = "yby_knowledge"
DEFAULT_ACCESS_LEVEL = "private"


@dataclass(frozen=True)
class IngestResult:
    """Compatível com testes anteriores (`content_sha256` = `content_hash`)."""

    source: str
    skipped: bool
    chunks_indexed: int
    content_sha256: str

    def to_model(self) -> IngestionResult:
        return IngestionResult(
            source=self.source,
            skipped=self.skipped,
            chunks_indexed=self.chunks_indexed,
            content_hash=self.content_sha256,
        )


@dataclass(frozen=True)
class IngestBatchSummary:
    indexed: int
    skipped: int
    failed: int
    results: list[IngestResult]


@dataclass
class _ManifestEntry:
    content_hash: str
    updated_at: str

    def to_json(self) -> dict[str, str]:
        return {"content_hash": self.content_hash, "updated_at": self.updated_at}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> _ManifestEntry:
        digest = str(data.get("content_hash") or data.get("content_sha256", ""))
        return cls(content_hash=digest, updated_at=str(data["updated_at"]))


class RagIngestor:
    """Indexa arquivos em data/knowledge somente."""

    def __init__(
        self,
        config: RagConfig | None = None,
        *,
        chroma_dir: Path | None = None,
        knowledge_dir: Path | None = None,
        collection_name: str | None = None,
        embed_model: BaseEmbedding | None = None,
        default_tags: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        if config is None:
            base = RagConfig.default()
            if chroma_dir is not None:
                chroma_path = Path(chroma_dir).resolve()
                knowledge_path = Path(knowledge_dir or chroma_path.parent).resolve()
                knowledge_path.mkdir(parents=True, exist_ok=True)
                config = RagConfig(
                    knowledge_dir=knowledge_path,
                    chroma_dir=chroma_path,
                    collection_name=collection_name or base.collection_name,
                    embed_model=base.embed_model,
                    ollama_base_url=base.ollama_base_url,
                    chunk_size_tokens=base.chunk_size_tokens,
                    chunk_overlap_tokens=base.chunk_overlap_tokens,
                    default_top_k=base.default_top_k,
                    max_results=base.max_results,
                    timeout_seconds=base.timeout_seconds,
                    max_file_bytes=base.max_file_bytes,
                    max_files_per_run=base.max_files_per_run,
                    default_access_level=base.default_access_level,
                )
            else:
                config = base
        self.config = config
        self.config.ensure_data_dirs()
        self.default_tags = default_tags or tags or []
        self._embed_model = create_embedder(self.config, override=embed_model)

        self._client = chromadb.PersistentClient(path=str(self.config.chroma_dir))
        self._chroma_collection = self._client.get_or_create_collection(self.config.collection_name)
        vector_store = ChromaVectorStore(chroma_collection=self._chroma_collection)
        self._storage = StorageContext.from_defaults(vector_store=vector_store)
        self._vector_store = vector_store

    @property
    def chroma_dir(self) -> Path:
        return self.config.chroma_dir

    @property
    def manifest_path(self) -> Path:
        return self.config.chroma_dir / MANIFEST_FILENAME

    @property
    def _collection(self) -> Any:
        return self._chroma_collection

    def ingest_paths(
        self,
        paths: list[Path | str] | None = None,
        *,
        force: bool = False,
    ) -> IngestBatchSummary:
        targets = self._collect_files(paths)
        if len(targets) > self.config.max_files_per_run:
            raise IngestionError(
                f"limite de {self.config.max_files_per_run} arquivos por execução excedido"
            )

        results: list[IngestResult] = []
        failed = 0
        for path in targets:
            try:
                results.append(self.ingest_file(path, force=force))
            except (UnsupportedDocumentError, IngestionError) as exc:
                failed += 1
                logger.error(
                    json.dumps(
                        {
                            "event": "ingest_failed",
                            "path": str(path),
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                        },
                        ensure_ascii=False,
                    )
                )
        indexed = sum(1 for item in results if not item.skipped and item.chunks_indexed > 0)
        skipped = sum(1 for item in results if item.skipped)
        return IngestBatchSummary(indexed=indexed, skipped=skipped, failed=failed, results=results)

    def ingest_file(self, path: Path | str, *, force: bool = False) -> IngestResult:
        candidate = Path(path)
        file_path = assert_knowledge_path(candidate, self.config.knowledge_dir)

        suffix = file_path.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise ValueError(f"tipo não suportado: {suffix}")

        content_hash = sha256_file(file_path, max_bytes=self.config.max_file_bytes)
        source_key = str(file_path)
        manifest = self._load_manifest()
        entry = manifest.get(source_key)

        if not force and entry and entry.content_hash == content_hash:
            return IngestResult(
                source=source_key,
                skipped=True,
                chunks_indexed=0,
                content_sha256=content_hash,
            )

        self._delete_source_chunks(source_key)

        document = load_document(
            file_path,
            access_level=self.config.default_access_level,
            default_tags=self.default_tags,
        )
        doc_type = str(document.metadata.get("doc_type", file_path.suffix.lstrip(".")))
        nodes = build_nodes(
            document.text,
            doc_type=doc_type,
            config=self.config,
            base_metadata=document.metadata,
        )
        nodes = attach_chunk_positions(nodes, content_hash=content_hash)

        if nodes:
            index = VectorStoreIndex.from_vector_store(
                vector_store=self._vector_store,
                storage_context=self._storage,
            )
            index.insert_nodes(nodes)

        manifest[source_key] = _ManifestEntry(
            content_hash=content_hash,
            updated_at=str(document.metadata.get("updated_at", "")),
        )
        self._save_manifest(manifest)

        logger.info(
            json.dumps(
                {
                    "event": "ingest_ok",
                    "source": source_key,
                    "chunks": len(nodes),
                    "content_hash": content_hash,
                },
                ensure_ascii=False,
            )
        )

        return IngestResult(
            source=source_key,
            skipped=False,
            chunks_indexed=len(nodes),
            content_sha256=content_hash,
        )

    def _collect_files(self, paths: list[Path | str] | None) -> list[Path]:
        knowledge_root = self.config.knowledge_dir.resolve()
        roots = [Path(item) for item in paths] if paths else [knowledge_root]

        collected: list[Path] = []
        for raw in roots:
            candidate = (
                raw
                if raw.is_absolute()
                else (knowledge_root / raw).resolve()
            )
            try:
                candidate.relative_to(knowledge_root)
            except ValueError as exc:
                raise UnsupportedDocumentError(
                    f"caminho fora de data/knowledge: {raw}"
                ) from exc

            if candidate.is_dir():
                for child in sorted(candidate.rglob("*")):
                    if child.is_file() and child.suffix.lower() in SUPPORTED_SUFFIXES:
                        collected.append(assert_knowledge_path(child, knowledge_root))
            elif candidate.is_file():
                collected.append(assert_knowledge_path(candidate, knowledge_root))
        return collected

    def _delete_source_chunks(self, source: str) -> None:
        try:
            self._collection.delete(where={"source": source})
        except (ValueError, TypeError):
            pass

    def _load_manifest(self) -> dict[str, _ManifestEntry]:
        if not self.manifest_path.is_file():
            return {}
        raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return {key: _ManifestEntry.from_json(value) for key, value in raw.items()}

    def _save_manifest(self, manifest: dict[str, _ManifestEntry]) -> None:
        payload = {key: entry.to_json() for key, entry in manifest.items()}
        self.manifest_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def ingest_paths(
    paths: list[Path | str] | None = None,
    *,
    config: RagConfig | None = None,
    force: bool = False,
    embed_model: BaseEmbedding | None = None,
) -> list[IngestResult]:
    summary = RagIngestor(config=config, embed_model=embed_model).ingest_paths(paths, force=force)
    return summary.results