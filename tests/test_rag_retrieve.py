"""Testes de recuperação RAG (Chroma + LlamaIndex)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("llama_index")
pytest.importorskip("chromadb")

from llama_index.core.embeddings import MockEmbedding

from src.yby.rag.ingest import RagIngestor
from src.yby.rag.retrieve import (
    RagRetriever,
    RetrieveHit,
    _build_context,
    _tags_match,
    search_knowledge,
)


@pytest.fixture
def mock_embedder() -> MockEmbedding:
    return MockEmbedding(embed_dim=64)


@pytest.fixture
def chroma_dir(tmp_path: Path) -> Path:
    return tmp_path / "chroma"


@pytest.fixture
def ingestor(chroma_dir: Path, mock_embedder: MockEmbedding) -> RagIngestor:
    return RagIngestor(chroma_dir=chroma_dir, embed_model=mock_embedder)


@pytest.fixture
def retriever(chroma_dir: Path, mock_embedder: MockEmbedding) -> RagRetriever:
    return RagRetriever(chroma_dir=chroma_dir, embed_model=mock_embedder)


def test_build_context_respects_limit() -> None:
    hits = [
        RetrieveHit(
            text="a" * 2000,
            score=1.0,
            source="/x/a.md",
            metadata={"chunk_index": 0},
        ),
        RetrieveHit(
            text="b" * 2000,
            score=0.5,
            source="/x/b.md",
            metadata={"chunk_index": 0},
        ),
    ]
    context, truncated, used = _build_context(hits, max_context_chars=500)
    assert truncated is True
    assert used <= 500
    assert len(context) <= 500


def test_tags_match_parses_json() -> None:
    assert _tags_match('["qa", "dev"]', ["qa"])
    assert not _tags_match('["qa"]', ["dev"])


def test_search_empty_query_raises(retriever: RagRetriever) -> None:
    with pytest.raises(ValueError, match="vazia"):
        retriever.search("   ")


@pytest.mark.integration
def test_retrieve_returns_chunk_metadata(
    ingestor: RagIngestor,
    retriever: RagRetriever,
    tmp_path: Path,
) -> None:
    path = tmp_path / "guia.md"
    path.write_text(
        "---\ntitle: Guia\ntags: arquitetura, local\n---\n"
        "# Guia\nO YBY SEED é local-first.\n",
        encoding="utf-8",
    )
    ingestor.ingest_file(path)

    result = retriever.search(
        "local-first",
        top_k=3,
        doc_type="md",
        tags=["arquitetura"],
        access_level="private",
        max_context_chars=2000,
    )

    assert result.hits
    hit = result.hits[0]
    assert hit.text
    assert hit.source == str(path.resolve())
    assert hit.score >= 0
    assert hit.metadata["doc_type"] == "md"
    assert hit.metadata["access_level"] == "private"
    assert json.loads(hit.metadata["tags"]) == ["arquitetura", "local"]
    assert result.context_text
    assert path.read_text() not in result.context_text
    assert result.context_chars <= result.max_context_chars


@pytest.mark.integration
def test_filter_doc_type_excludes_other_types(
    ingestor: RagIngestor,
    retriever: RagRetriever,
    tmp_path: Path,
) -> None:
    md = tmp_path / "a.md"
    txt = tmp_path / "b.txt"
    md.write_text("# A\nmarkdown", encoding="utf-8")
    txt.write_text("texto plano", encoding="utf-8")
    ingestor.ingest_file(md)
    ingestor.ingest_file(txt)

    result = retriever.search("texto", top_k=5, doc_type="txt")
    assert all(hit.metadata.get("doc_type") == "txt" for hit in result.hits)


@pytest.mark.integration
def test_top_k_limits_hits(
    ingestor: RagIngestor,
    retriever: RagRetriever,
    tmp_path: Path,
) -> None:
    for index in range(4):
        file_path = tmp_path / f"n{index}.txt"
        file_path.write_text(f"conteúdo tema delta número {index}", encoding="utf-8")
        ingestor.ingest_file(file_path)

    result = retriever.search("tema delta", top_k=2)
    assert len(result.hits) <= 2


@pytest.mark.integration
def test_search_knowledge_module_helper(
    chroma_dir: Path,
    ingestor: RagIngestor,
    mock_embedder: MockEmbedding,
    tmp_path: Path,
) -> None:
    doc = tmp_path / "helper.md"
    doc.write_text("# T\nconsulta helper", encoding="utf-8")
    ingestor.ingest_file(doc)

    result = search_knowledge(
        "consulta",
        chroma_dir=chroma_dir,
        top_k=1,
        embed_model=mock_embedder,
    )
    assert result.hits[0].metadata["title"] == "T"