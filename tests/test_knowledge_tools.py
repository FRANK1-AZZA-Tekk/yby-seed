"""Testes da ferramenta search_knowledge."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("llama_index")
pytest.importorskip("chromadb")

from llama_index.core.embeddings import MockEmbedding

from src.yby.rag.config import RagConfig
from src.yby.rag.ingest import RagIngestor
from src.yby.rag.retrieve import RagRetriever
from src.yby.tools.registry import create_default_registry

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "documents"


@pytest.fixture
def mock_embedder() -> MockEmbedding:
    return MockEmbedding(embed_dim=64)


@pytest.fixture
def rag_stack(tmp_path: Path, mock_embedder: MockEmbedding) -> tuple[RagConfig, RagIngestor, RagRetriever]:
    knowledge = tmp_path / "knowledge"
    chroma = tmp_path / "chroma"
    knowledge.mkdir()
    chroma.mkdir()
    base = RagConfig.default()
    cfg = RagConfig(
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
        max_context_chars=base.max_context_chars,
    )
    ingestor = RagIngestor(cfg, embed_model=mock_embedder)
    retriever = RagRetriever(cfg, embed_model=mock_embedder)
    return cfg, ingestor, retriever


@pytest.mark.integration
def test_search_knowledge_returns_hits_and_metadata(
    rag_stack: tuple[RagConfig, RagIngestor, RagRetriever],
    mock_embedder: MockEmbedding,
) -> None:
    cfg, ingestor, retriever = rag_stack
    root = cfg.knowledge_dir
    shutil.copy(FIXTURES / "sample.md", root / "sample.md")
    ingestor.ingest_file(root / "sample.md")

    registry = create_default_registry(read_roots=[root], rag_retriever=retriever)
    response = registry.run(
        "search_knowledge",
        {"query": "ingestão português", "top_k": 2, "tags": ["qa"]},
    )
    assert response.ok is True
    assert response.data is not None
    hits = response.data["hits"]
    assert hits
    hit = hits[0]
    assert hit["source"] == "sample.md"
    assert hit["doc_type"] == "md"
    assert hit["title"]
    assert hit["content_hash"]
    assert response.data["context_text"]
    assert Path(hit["source"]).is_absolute() is False


@pytest.mark.integration
def test_search_knowledge_empty_index_structured_error(
    rag_stack: tuple[RagConfig, RagIngestor, RagRetriever],
) -> None:
    _, _, retriever = rag_stack
    registry = create_default_registry(read_roots=[retriever.knowledge_dir], rag_retriever=retriever)
    response = registry.run("search_knowledge", {"query": "algo"})
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "execution_error"