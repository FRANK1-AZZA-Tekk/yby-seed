"""Testes da fundação RAG (config, models, errors)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.yby.rag.config import RagConfig
from src.yby.rag.errors import ConfigurationError, IngestionError, RagError, RetrievalError
from src.yby.rag.models import DocumentMetadata, IngestionResult, RagConfig as RagConfigSchema


def test_default_config_values() -> None:
    cfg = RagConfig.default()
    assert cfg.chunk_size_tokens == 800
    assert cfg.chunk_overlap_tokens == 120
    assert cfg.chunk_overlap_ratio == pytest.approx(0.15)
    assert cfg.default_top_k == 5
    assert cfg.max_results == 10
    assert cfg.timeout_seconds == 30.0
    assert cfg.collection_name == "yby_knowledge"
    assert cfg.embed_model == "nomic-embed-text"
    assert cfg.ollama_base_url == "http://localhost:11434"
    assert cfg.knowledge_dir.name == "knowledge"
    assert cfg.chroma_dir.name == "chroma"


def test_config_rejects_overlap_ge_size() -> None:
    with pytest.raises(ConfigurationError, match="chunk_overlap"):
        RagConfig(
            knowledge_dir=RagConfig.default().knowledge_dir,
            chroma_dir=RagConfig.default().chroma_dir,
            collection_name="yby_knowledge",
            embed_model="nomic-embed-text",
            ollama_base_url="http://localhost:11434",
            chunk_size_tokens=100,
            chunk_overlap_tokens=100,
            default_top_k=5,
            max_results=10,
            timeout_seconds=30.0,
        )


def test_config_rejects_top_k_above_max_results() -> None:
    base = RagConfig.default()
    with pytest.raises(ConfigurationError, match="default_top_k"):
        RagConfig(
            knowledge_dir=base.knowledge_dir,
            chroma_dir=base.chroma_dir,
            collection_name=base.collection_name,
            embed_model=base.embed_model,
            ollama_base_url=base.ollama_base_url,
            chunk_size_tokens=base.chunk_size_tokens,
            chunk_overlap_tokens=base.chunk_overlap_tokens,
            default_top_k=11,
            max_results=10,
            timeout_seconds=base.timeout_seconds,
        )


def test_config_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("YBY_RAG_KNOWLEDGE_DIR", str(tmp_path / "know"))
    monkeypatch.setenv("YBY_RAG_CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("YBY_RAG_TOP_K", "3")
    monkeypatch.setenv("YBY_RAG_TIMEOUT", "45")

    cfg = RagConfig.from_env(load_dotenv_file=False)
    assert cfg.knowledge_dir == (tmp_path / "know").resolve()
    assert cfg.chroma_dir == (tmp_path / "chroma").resolve()
    assert cfg.default_top_k == 3
    assert cfg.timeout_seconds == 45.0


def test_document_metadata_requires_fields() -> None:
    now = datetime.now(tz=UTC)
    meta = DocumentMetadata(
        source="/docs/DEV.md",
        title="Dev",
        doc_type="md",
        language="pt-BR",
        created_at=now,
        updated_at=now,
        tags=["seed"],
        access_level="private",
        chunk_index=0,
        chunk_total=2,
        content_hash="a" * 64,
    )
    assert meta.source.endswith("DEV.md")
    assert meta.chunk_index < meta.chunk_total


def test_document_metadata_rejects_bad_hash() -> None:
    now = datetime.now(tz=UTC)
    with pytest.raises(ValueError, match="content_hash"):
        DocumentMetadata(
            source="x.md",
            title="t",
            doc_type="md",
            language="pt-BR",
            created_at=now,
            updated_at=now,
            chunk_index=0,
            chunk_total=1,
            content_hash="not-hex",
        )


def test_ingestion_result_model() -> None:
    result = IngestionResult(
        source="/docs/a.md",
        skipped=False,
        chunks_indexed=3,
        content_hash="b" * 64,
    )
    assert result.chunks_indexed == 3


def test_rag_config_schema_from_defaults() -> None:
    cfg = RagConfig.default()
    schema = RagConfigSchema(
        knowledge_dir=str(cfg.knowledge_dir),
        chroma_dir=str(cfg.chroma_dir),
        collection_name=cfg.collection_name,
        embed_model=cfg.embed_model,
        ollama_base_url=cfg.ollama_base_url,
        chunk_size_tokens=cfg.chunk_size_tokens,
        chunk_overlap_tokens=cfg.chunk_overlap_tokens,
        default_top_k=cfg.default_top_k,
        max_results=cfg.max_results,
        timeout_seconds=cfg.timeout_seconds,
    )
    assert schema.collection_name == "yby_knowledge"


def test_error_hierarchy() -> None:
    assert issubclass(IngestionError, RagError)
    assert issubclass(RetrievalError, RagError)