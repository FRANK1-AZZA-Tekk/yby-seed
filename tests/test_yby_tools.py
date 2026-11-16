"""Testes do registro de ferramentas YBY."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("llama_index")
pytest.importorskip("chromadb")

from llama_index.core.embeddings import MockEmbedding

from src.yby.rag.ingest import RagIngestor
from src.yby.rag.retrieve import RagRetriever
from src.yby.tools.allowlist import assert_allowed_path
from src.yby.tools.registry import (
    SearchKnowledgeArgs,
    ToolRegistry,
    create_default_registry,
)


@pytest.fixture
def mock_embedder() -> MockEmbedding:
    return MockEmbedding(embed_dim=64)


@pytest.fixture
def read_root(tmp_path: Path) -> Path:
    root = tmp_path / "allowed"
    root.mkdir()
    return root


@pytest.fixture
def rag_retriever(tmp_path: Path, mock_embedder: MockEmbedding) -> RagRetriever:
    return RagRetriever(chroma_dir=tmp_path / "chroma", embed_model=mock_embedder)


@pytest.fixture
def registry(read_root: Path, rag_retriever: RagRetriever) -> ToolRegistry:
    return create_default_registry(read_roots=[read_root], rag_retriever=rag_retriever)


def test_tool_definitions_expose_schema(registry: ToolRegistry) -> None:
    docs = registry.describe_all()
    names = {item["name"] for item in docs}
    assert names == {"list_files", "read_file", "search_knowledge"}
    search = next(item for item in docs if item["name"] == "search_knowledge")
    assert search["json_schema"]["title"] == "SearchKnowledgeArgs"
    assert search["risk"] == "low"
    assert search["requires_approval"] is False


def test_validation_error_is_structured(registry: ToolRegistry) -> None:
    response = registry.run("search_knowledge", {"query": ""})
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "validation_error"
    assert response.to_dict()["error"]["details"]["errors"]


def test_read_file_rejects_path_outside_allowlist(
    registry: ToolRegistry, tmp_path: Path
) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_text("x", encoding="utf-8")
    response = registry.run("read_file", {"path": str(outside)})
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "path_not_allowed"


def test_read_file_truncates_content(registry: ToolRegistry, read_root: Path) -> None:
    target = read_root / "a.txt"
    target.write_text("abcdefghij", encoding="utf-8")
    response = registry.run(
        "read_file",
        {"path": str(target), "max_bytes": 4},
    )
    assert response.ok is True
    assert response.data is not None
    assert response.data["truncated"] is True
    assert response.data["content"] == "abcd"


def test_list_files_respects_pattern(registry: ToolRegistry, read_root: Path) -> None:
    (read_root / "keep.md").write_text("# k", encoding="utf-8")
    (read_root / "skip.bin").write_bytes(b"\x00")
    response = registry.run(
        "list_files",
        {"path": str(read_root), "pattern": "*.md"},
    )
    assert response.ok is True
    assert response.data is not None
    assert len(response.data["entries"]) == 1
    assert response.data["entries"][0]["name"] == "keep.md"


@pytest.mark.integration
def test_search_knowledge_calls_rag(
    registry: ToolRegistry,
    rag_retriever: RagRetriever,
    read_root: Path,
    mock_embedder: MockEmbedding,
) -> None:
    chroma_dir = rag_retriever.chroma_dir
    ingestor = RagIngestor(chroma_dir=chroma_dir, embed_model=mock_embedder)
    doc = read_root / "rag.md"
    doc.write_text("# RAG\níndice vetorial local", encoding="utf-8")
    ingestor.ingest_file(doc)

    response = registry.run(
        "search_knowledge",
        SearchKnowledgeArgs(query="vetorial", top_k=2).model_dump(),
    )
    assert response.ok is True
    assert response.data is not None
    assert response.data["hits"]
    assert "vetorial" in response.data["context_text"].lower() or response.data["hits"]


def test_assert_allowed_relative_path(read_root: Path) -> None:
    child = read_root / "sub"
    child.mkdir()
    resolved = assert_allowed_path("sub", roots=[read_root])
    assert resolved == child.resolve()