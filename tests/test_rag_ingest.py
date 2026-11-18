"""Testes de ingestão RAG (Tarefa 2)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("llama_index")
pytest.importorskip("chromadb")

from llama_index.core.embeddings import MockEmbedding

from src.yby.rag.config import RagConfig
from src.yby.rag.errors import UnsupportedDocumentError
from src.yby.rag.ingest import RagIngestor
from src.yby.rag.loaders import assert_knowledge_path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "documents"


@pytest.fixture
def mock_embedder() -> MockEmbedding:
    return MockEmbedding(embed_dim=64)


@pytest.fixture
def rag_config(tmp_path: Path) -> RagConfig:
    knowledge = tmp_path / "knowledge"
    chroma = tmp_path / "chroma"
    knowledge.mkdir()
    chroma.mkdir()
    base = RagConfig.default()
    return RagConfig(
        knowledge_dir=knowledge,
        chroma_dir=chroma,
        collection_name=base.collection_name,
        embed_model=base.embed_model,
        ollama_base_url=base.ollama_base_url,
        chunk_size_tokens=base.chunk_size_tokens,
        chunk_overlap_tokens=base.chunk_overlap_tokens,
        default_top_k=base.default_top_k,
        max_results=base.max_results,
        timeout_seconds=base.timeout_seconds,
        max_file_bytes=base.max_file_bytes,
        max_files_per_run=base.max_files_per_run,
    )


@pytest.fixture
def ingestor(rag_config: RagConfig, mock_embedder: MockEmbedding) -> RagIngestor:
    return RagIngestor(rag_config, embed_model=mock_embedder)


def _copy_fixture(name: str, knowledge_dir: Path) -> Path:
    target = knowledge_dir / name
    shutil.copy(FIXTURES / name, target)
    return target


def test_ingest_markdown_metadata(ingestor: RagIngestor, rag_config: RagConfig) -> None:
    path = _copy_fixture("sample.md", rag_config.knowledge_dir)
    result = ingestor.ingest_file(path)
    assert result.skipped is False
    assert result.chunks_indexed >= 1

    row = ingestor._collection.get(include=["metadatas"])  # noqa: SLF001
    meta = row["metadatas"][0]
    assert meta["title"] == "Documento de Teste"
    assert meta["doc_type"] == "md"
    assert meta["language"] in {"pt-BR", "und"}
    assert meta["chunk_index"] == 0
    assert meta["chunk_total"] == result.chunks_indexed
    assert len(meta["content_hash"]) == 64
    assert json.loads(meta["tags"]) == ["qa", "ingest"]


def test_ingest_txt(ingestor: RagIngestor, rag_config: RagConfig) -> None:
    path = _copy_fixture("sample.txt", rag_config.knowledge_dir)
    result = ingestor.ingest_file(path)
    assert result.chunks_indexed >= 1
    meta = ingestor._collection.get(include=["metadatas"])["metadatas"][0]  # noqa: SLF001
    assert meta["doc_type"] == "txt"


def test_deduplication_by_content_hash(ingestor: RagIngestor, rag_config: RagConfig) -> None:
    path = _copy_fixture("sample.txt", rag_config.knowledge_dir)
    first = ingestor.ingest_file(path)
    second = ingestor.ingest_file(path)
    assert first.skipped is False
    assert second.skipped is True
    count = ingestor._collection.count()  # noqa: SLF001
    assert count == first.chunks_indexed


def test_reindex_after_change(ingestor: RagIngestor, rag_config: RagConfig) -> None:
    path = _copy_fixture("sample.txt", rag_config.knowledge_dir)
    ingestor.ingest_file(path)
    before = ingestor._collection.count()  # noqa: SLF001
    path.write_text("conteúdo atualizado para forçar novo hash", encoding="utf-8")
    again = ingestor.ingest_file(path)
    assert again.skipped is False
    after = ingestor._collection.count()  # noqa: SLF001
    assert after >= 1
    assert after <= before + 5


def test_reject_path_outside_knowledge(rag_config: RagConfig, tmp_path: Path) -> None:
    outside = tmp_path / "externo.txt"
    outside.write_text("fora", encoding="utf-8")
    with pytest.raises(UnsupportedDocumentError, match="fora de data/knowledge"):
        assert_knowledge_path(outside, rag_config.knowledge_dir)


def test_reject_unsupported_type(ingestor: RagIngestor, rag_config: RagConfig) -> None:
    bad = rag_config.knowledge_dir / "dados.bin"
    bad.write_bytes(b"\x00\x01")
    with pytest.raises(ValueError, match="não suportado"):
        ingestor.ingest_file(bad)


def test_chroma_persistence(rag_config: RagConfig, mock_embedder: MockEmbedding) -> None:
    path = _copy_fixture("sample.md", rag_config.knowledge_dir)
    first = RagIngestor(rag_config, embed_model=mock_embedder)
    first.ingest_file(path)
    count_first = first._collection.count()  # noqa: SLF001

    second = RagIngestor(rag_config, embed_model=mock_embedder)
    assert second._collection.count() == count_first  # noqa: SLF001
    skip = second.ingest_file(path)
    assert skip.skipped is True