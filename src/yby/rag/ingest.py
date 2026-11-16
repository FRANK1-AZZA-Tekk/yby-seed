"""Ingestão de documentos no índice vetorial Chroma (LlamaIndex + Ollama)."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import BaseNode
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.readers.file import PDFReader
from llama_index.vector_stores.chroma import ChromaVectorStore

import chromadb

DocType = Literal["md", "txt", "pdf"]

CHUNK_SIZE_TOKENS = 800
CHUNK_OVERLAP_TOKENS = int(CHUNK_SIZE_TOKENS * 0.15)
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_CHROMA_DIR = Path("data/chroma")
DEFAULT_COLLECTION_NAME = "yby_knowledge_v1"
MANIFEST_FILENAME = "ingest_manifest.json"
DEFAULT_ACCESS_LEVEL = "private"
SUPPORTED_SUFFIXES = frozenset({".md", ".txt", ".pdf"})

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_TITLE_MD = re.compile(r"^#\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class IngestResult:
    source: str
    skipped: bool
    chunks_indexed: int
    content_sha256: str


@dataclass
class _ManifestEntry:
    content_sha256: str
    updated_at: str

    def to_json(self) -> dict[str, str]:
        return {
            "content_sha256": self.content_sha256,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> _ManifestEntry:
        return cls(
            content_sha256=str(data["content_sha256"]),
            updated_at=str(data["updated_at"]),
        )


class RagIngestor:
    """Indexa arquivos .md / .txt / .pdf em Chroma persistente."""

    def __init__(
        self,
        *,
        chroma_dir: Path | None = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        embed_model: BaseEmbedding | None = None,
        ollama_base_url: str | None = None,
        embed_model_name: str = DEFAULT_EMBED_MODEL,
        access_level: str = DEFAULT_ACCESS_LEVEL,
        tags: list[str] | None = None,
    ) -> None:
        self.chroma_dir = (chroma_dir or DEFAULT_CHROMA_DIR).resolve()
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.access_level = access_level
        self.tags = tags or []

        base_url = ollama_base_url or os.getenv("YBY_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self._embed_model = embed_model or OllamaEmbedding(
            model_name=embed_model_name,
            base_url=base_url,
        )
        Settings.embed_model = self._embed_model

        self._client = chromadb.PersistentClient(path=str(self.chroma_dir))
        self._collection = self._client.get_or_create_collection(self.collection_name)
        self._vector_store = ChromaVectorStore(chroma_collection=self._collection)
        self._storage_context = StorageContext.from_defaults(vector_store=self._vector_store)
        self._splitter = SentenceSplitter(
            chunk_size=CHUNK_SIZE_TOKENS,
            chunk_overlap=CHUNK_OVERLAP_TOKENS,
        )
        self._pdf_reader = PDFReader()

    @property
    def manifest_path(self) -> Path:
        return self.chroma_dir / MANIFEST_FILENAME

    def ingest_paths(self, paths: list[Path | str], *, force: bool = False) -> list[IngestResult]:
        results: list[IngestResult] = []
        for raw in paths:
            path = Path(raw).resolve()
            if path.is_dir():
                for child in sorted(path.rglob("*")):
                    if child.is_file() and child.suffix.lower() in SUPPORTED_SUFFIXES:
                        results.append(self.ingest_file(child, force=force))
            elif path.is_file():
                results.append(self.ingest_file(path, force=force))
        return results

    def ingest_file(self, path: Path | str, *, force: bool = False) -> IngestResult:
        file_path = Path(path).resolve()
        suffix = file_path.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise ValueError(f"tipo não suportado: {suffix}")

        content_hash = _sha256_file(file_path)
        manifest = self._load_manifest()
        source_key = str(file_path)
        entry = manifest.get(source_key)
        if not force and entry and entry.content_sha256 == content_hash:
            return IngestResult(
                source=source_key,
                skipped=True,
                chunks_indexed=0,
                content_sha256=content_hash,
            )

        self._delete_source_chunks(source_key)

        document = self._load_document(file_path)
        nodes = self._splitter.get_nodes_from_documents([document])
        nodes = self._enrich_nodes(
            nodes,
            file_path=file_path,
            content_hash=content_hash,
        )
        if nodes:
            index = VectorStoreIndex.from_vector_store(
                vector_store=self._vector_store,
                storage_context=self._storage_context,
            )
            index.insert_nodes(nodes)

        stat = file_path.stat()
        manifest[source_key] = _ManifestEntry(
            content_sha256=content_hash,
            updated_at=_iso_from_timestamp(stat.st_mtime),
        )
        self._save_manifest(manifest)

        return IngestResult(
            source=source_key,
            skipped=False,
            chunks_indexed=len(nodes),
            content_sha256=content_hash,
        )

    def _load_document(self, path: Path) -> Document:
        suffix = path.suffix.lower()
        doc_type: DocType = suffix.lstrip(".")  # type: ignore[assignment]
        stat = path.stat()
        created_at = _iso_from_timestamp(stat.st_ctime)
        updated_at = _iso_from_timestamp(stat.st_mtime)
        source = str(path)

        if suffix == ".pdf":
            pages = self._pdf_reader.load_data(file=path)
            text = "\n\n".join(page.text for page in pages if page.text)
            title = path.stem
            tags = list(self.tags)
            language = _guess_language(text)
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            title, tags, language = _metadata_from_text(text, path, self.tags)

        base_meta = {
            "source": source,
            "title": title,
            "doc_type": doc_type,
            "language": language,
            "created_at": created_at,
            "updated_at": updated_at,
            "tags": _tags_to_chroma(tags),
            "access_level": self.access_level,
        }
        return Document(text=text, metadata=base_meta)

    def _enrich_nodes(self, nodes: list[BaseNode], *, file_path: Path, content_hash: str) -> list[BaseNode]:
        total = len(nodes)
        for index, node in enumerate(nodes):
            node.metadata.setdefault("source", str(file_path))
            node.metadata.setdefault("access_level", self.access_level)
            node.metadata["chunk_index"] = index
            node.metadata["chunk_total"] = total
            if "tags" in node.metadata:
                node.metadata["tags"] = _tags_to_chroma(_tags_from_chroma(node.metadata["tags"]))
        return nodes

    def _delete_source_chunks(self, source: str) -> None:
        try:
            self._collection.delete(where={"source": source})
        except (ValueError, TypeError):
            # Collection vazia ou API sem matches.
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
    paths: list[Path | str],
    *,
    chroma_dir: Path | None = None,
    force: bool = False,
    embed_model: BaseEmbedding | None = None,
) -> list[IngestResult]:
    ingestor = RagIngestor(chroma_dir=chroma_dir, embed_model=embed_model)
    return ingestor.ingest_paths(paths, force=force)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _iso_from_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def _guess_language(text: str) -> str:
    sample = text[:2000].lower()
    pt_hits = sum(
        1
        for token in ("ção", " não ", " para ", " você ", " são ")
        if token in sample
    )
    return "pt-BR" if pt_hits >= 2 else "und"


def _metadata_from_text(text: str, path: Path, default_tags: list[str]) -> tuple[str, list[str], str]:
    body = text
    tags = list(default_tags)
    title = path.stem

    match = _FRONTMATTER.match(text)
    if match:
        block = match.group(1)
        body = text[match.end() :]
        for line in block.splitlines():
            if line.lower().startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"')
            elif line.lower().startswith("tags:"):
                raw = line.split(":", 1)[1].strip()
                tags = [part.strip() for part in raw.split(",") if part.strip()]

    heading = _TITLE_MD.search(body)
    if heading and title == path.stem:
        title = heading.group(1).strip()

    language = _guess_language(body)
    return title, tags, language


def _tags_to_chroma(tags: list[str]) -> str:
    return json.dumps(tags, ensure_ascii=False)


def _tags_from_chroma(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [part.strip() for part in value.split(",") if part.strip()]
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return []