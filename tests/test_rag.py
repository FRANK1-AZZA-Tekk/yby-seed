"""Testes do RAG (ingestão Chroma + LlamaIndex; legado LanceDB com skip)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("llama_index")
pytest.importorskip("chromadb")

from llama_index.core.embeddings import MockEmbedding

from src.yby.rag.ingest import (
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
    IngestResult,
    RagIngestor,
    _metadata_from_text,
    _tags_to_chroma,
)


@pytest.fixture
def mock_embedder() -> MockEmbedding:
    return MockEmbedding(embed_dim=64)


@pytest.fixture
def ingestor(tmp_path: Path, mock_embedder: MockEmbedding) -> RagIngestor:
    chroma_dir = tmp_path / "chroma"
    return RagIngestor(chroma_dir=chroma_dir, embed_model=mock_embedder, tags=["seed"])


def _write_note(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_chunk_constants_match_requirements() -> None:
    assert CHUNK_SIZE_TOKENS == 800
    assert CHUNK_OVERLAP_TOKENS == 120


def test_ingest_file_indexes_markdown_with_metadata(
    ingestor: RagIngestor, tmp_path: Path
) -> None:
    md = (
      "---\ntitle: Nota Teste\ntags: qa, dev\n---\n"
        "# Cabeçalho\nConteúdo da nota para o índice vetorial.\n"
    )
    path = _write_note(tmp_path, "nota.md", md)
    result = ingestor.ingest_file(path)
    assert result.skipped is False
    assert result.chunks_indexed >= 1

    row = ingestor._collection.get(include=["metadatas"])  # noqa: SLF001
    meta = row["metadatas"][0]
    assert meta["source"] == str(path.resolve())
    assert meta["title"] == "Nota Teste"
    assert meta["doc_type"] == "md"
    assert meta["language"] in {"pt-BR", "und"}
    assert "created_at" in meta
    assert "updated_at" in meta
    assert json.loads(meta["tags"]) == ["qa", "dev"]
    assert meta["access_level"] == "private"
    assert meta["chunk_index"] == 0
    assert meta["chunk_total"] == result.chunks_indexed


def test_ingest_skips_unchanged_document(ingestor: RagIngestor, tmp_path: Path) -> None:
    path = _write_note(tmp_path, "estavel.txt", "texto estável")
    first = ingestor.ingest_file(path)
    second = ingestor.ingest_file(path)
    assert first.skipped is False
    assert second.skipped is True
    assert second == IngestResult(
        source=str(path.resolve()),
        skipped=True,
        chunks_indexed=0,
        content_sha256=first.content_sha256,
    )


def test_ingest_reindexes_when_content_changes(ingestor: RagIngestor, tmp_path: Path) -> None:
    path = _write_note(tmp_path, "mutavel.txt", "versão um")
    ingestor.ingest_file(path)
    path.write_text("versão dois com mais dados para reindexar", encoding="utf-8")
    again = ingestor.ingest_file(path)
    assert again.skipped is False
    assert again.chunks_indexed >= 1


def test_ingest_force_reindexes_without_content_change(
    ingestor: RagIngestor, tmp_path: Path
) -> None:
    path = _write_note(tmp_path, "forcar.txt", "mesmo texto")
    ingestor.ingest_file(path)
    forced = ingestor.ingest_file(path, force=True)
    assert forced.skipped is False
    assert forced.chunks_indexed >= 1


def test_ingest_txt_assigns_doc_type_and_title(ingestor: RagIngestor, tmp_path: Path) -> None:
    path = _write_note(tmp_path, "leitura.txt", "Arquivo simples.")
    ingestor.ingest_file(path)
    meta = ingestor._collection.get(include=["metadatas"])["metadatas"][0]  # noqa: SLF001
    assert meta["doc_type"] == "txt"
    assert meta["title"] == "leitura"


def test_unsupported_suffix_raises(ingestor: RagIngestor, tmp_path: Path) -> None:
    bad = tmp_path / "dados.bin"
    bad.write_bytes(b"\x00\x01")
    with pytest.raises(ValueError, match="não suportado"):
        ingestor.ingest_file(bad)


def test_metadata_helper_tags_serialization() -> None:
    assert _tags_to_chroma(["a", "b"]) == '["a", "b"]'
    title, tags, lang = _metadata_from_text("# Título\nOlá mundo", Path("x.md"), ["seed"])
    assert title == "Título"
    assert "seed" in tags or tags == []
    assert lang in {"pt-BR", "und"}


@pytest.mark.skip(reason="RAG legado LanceDB — fora do escopo Chroma ingest")
@pytest.mark.integration
def test_rag_chunking_ast(sample_skill_manifest, mock_lancedb):
    pass


@pytest.mark.skip(reason="RAG legado LanceDB — fora do escopo Chroma ingest")
@pytest.mark.integration
def test_rag_context_pruning(sample_user_command, mock_lancedb):
    pass


@pytest.mark.skip(reason="RAG legado LanceDB — fora do escopo Chroma ingest")
@pytest.mark.integration
def test_rag_recupera_contexto_relevante(sample_user_command, mock_lancedb):
    pass