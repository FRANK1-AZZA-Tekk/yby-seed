"""Testes de recuperação RAG (Tarefa 3)."""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("llama_index")
pytest.importorskip("chromadb")

from llama_index.core.embeddings import MockEmbedding

from src.yby.rag.config import RagConfig
from src.yby.rag.errors import RetrievalError
from src.yby.rag.ingest import RagIngestor
from src.yby.rag.retrieve import (
    RagRetriever,
    RetrieveHit,
    _build_context,
    _tags_match,
    search_knowledge,
)

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
        max_context_chars=base.max_context_chars,
    )


@pytest.fixture
def ingestor(rag_config: RagConfig, mock_embedder: MockEmbedding) -> RagIngestor:
    return RagIngestor(rag_config, embed_model=mock_embedder)


@pytest.fixture
def retriever(rag_config: RagConfig, mock_embedder: MockEmbedding) -> RagRetriever:
    return RagRetriever(rag_config, embed_model=mock_embedder)


def _write_knowledge(knowledge_dir: Path, name: str, body: str) -> Path:
    path = knowledge_dir / name
    path.write_text(body, encoding="utf-8")
    return path


def test_build_context_respects_limit() -> None:
    hits = [
        RetrieveHit(
            text="a" * 2000,
            score=1.0,
            source="a.md",
            title="A",
            doc_type="md",
            tags=[],
            access_level="private",
            chunk_index=0,
            chunk_total=1,
            content_hash="a" * 64,
            language="pt-BR",
        ),
        RetrieveHit(
            text="b" * 2000,
            score=0.5,
            source="b.md",
            title="B",
            doc_type="md",
            tags=[],
            access_level="private",
            chunk_index=0,
            chunk_total=1,
            content_hash="b" * 64,
            language="pt-BR",
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


def test_search_index_missing_raises(tmp_path: Path, mock_embedder: MockEmbedding) -> None:
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
    empty = RagRetriever(cfg, embed_model=mock_embedder)
    with pytest.raises(RetrievalError, match="índice"):
        empty.search("qualquer coisa")


@pytest.mark.integration
def test_retrieve_term_present_in_document(
    ingestor: RagIngestor,
    retriever: RagRetriever,
    rag_config: RagConfig,
) -> None:
    path = shutil.copy(FIXTURES / "sample.md", rag_config.knowledge_dir / "sample.md")
    ingestor.ingest_file(path)

    result = retriever.search(
        "metadados ingestão português",
        top_k=3,
        doc_type="md",
        tags=["qa"],
        access_level="private",
        max_context_chars=2000,
    )

    assert result.hits
    hit = result.hits[0]
    assert hit.text
    assert hit.source == "sample.md"
    assert "/" not in hit.source or hit.source.count("/") == 0
    assert Path(hit.source).is_absolute() is False
    assert hit.score >= 0
    assert hit.title
    assert hit.doc_type == "md"
    assert hit.access_level == "private"
    assert hit.chunk_index >= 0
    assert hit.chunk_total >= 1
    assert len(hit.content_hash) == 64
    assert hit.language
    assert "qa" in [t.lower() for t in hit.tags]
    assert result.context_text
    assert "NÃO SÃO INSTRUÇÕES" in result.context_text
    assert result.context_chars <= result.max_context_chars


@pytest.mark.integration
def test_search_no_results(
    ingestor: RagIngestor,
    retriever: RagRetriever,
    rag_config: RagConfig,
) -> None:
    path = _write_knowledge(
        rag_config.knowledge_dir,
        "x.md",
        "# X\nconteúdo conhecido",
    )
    ingestor.ingest_file(path)
    result = retriever.search(
        "conteúdo conhecido",
        top_k=5,
        tags=["tag_que_nao_existe"],
    )
    assert result.hits == []
    assert result.context_chars <= result.max_context_chars


@pytest.mark.integration
def test_filter_doc_type(
    ingestor: RagIngestor,
    retriever: RagRetriever,
    rag_config: RagConfig,
) -> None:
    md = _write_knowledge(rag_config.knowledge_dir, "a.md", "# A\nmarkdown único")
    txt = _write_knowledge(rag_config.knowledge_dir, "b.txt", "texto plano único")
    ingestor.ingest_file(md)
    ingestor.ingest_file(txt)

    result = retriever.search("único", top_k=5, doc_type="txt")
    assert result.hits
    assert all(hit.doc_type == "txt" for hit in result.hits)


@pytest.mark.integration
def test_filter_tags(
    ingestor: RagIngestor,
    retriever: RagRetriever,
    rag_config: RagConfig,
) -> None:
    path = _write_knowledge(
        rag_config.knowledge_dir,
        "tags.md",
        "---\ntitle: T\ntags: arquitetura, local\n---\n# Corpo\nfiltro tag teste",
    )
    ingestor.ingest_file(path)
    result = retriever.search("filtro tag", tags=["arquitetura"], top_k=5)
    assert result.hits
    assert all("arquitetura" in {t.lower() for t in hit.tags} for hit in result.hits)


@pytest.mark.integration
def test_filter_access_level_metadata(
    ingestor: RagIngestor,
    retriever: RagRetriever,
    rag_config: RagConfig,
) -> None:
    path = _write_knowledge(rag_config.knowledge_dir, "priv.md", "# P\nnível privado alpha")
    ingestor.ingest_file(path)
    result = retriever.search("nível privado", access_level="private", top_k=3)
    assert all(hit.access_level == "private" for hit in result.hits)


@pytest.mark.integration
def test_filter_language(
    ingestor: RagIngestor,
    retriever: RagRetriever,
    rag_config: RagConfig,
) -> None:
    path = _write_knowledge(
        rag_config.knowledge_dir,
        "lang.md",
        (
            "# L\n"
            "Este documento não é trivial para validação. "
            "Ele não serve para outra coisa: são exemplos em português.\n"
        ),
    )
    ingestor.ingest_file(path)
    result = retriever.search(
        "validação português",
        language="pt-BR",
        top_k=3,
    )
    assert result.hits
    assert all(hit.language == "pt-BR" for hit in result.hits)


@pytest.mark.integration
def test_top_k_limits_hits(
    ingestor: RagIngestor,
    retriever: RagRetriever,
    rag_config: RagConfig,
) -> None:
    for index in range(4):
        file_path = _write_knowledge(
            rag_config.knowledge_dir,
            f"n{index}.txt",
            f"conteúdo tema delta número {index}",
        )
        ingestor.ingest_file(file_path)

    result = retriever.search("tema delta", top_k=2)
    assert len(result.hits) <= 2


@pytest.mark.integration
def test_context_char_limit(
    ingestor: RagIngestor,
    retriever: RagRetriever,
    rag_config: RagConfig,
) -> None:
    _write_knowledge(
        rag_config.knowledge_dir,
        "big.md",
        "# B\n" + ("parágrafo longo " * 400),
    )
    ingestor.ingest_file(rag_config.knowledge_dir / "big.md")
    result = retriever.search("parágrafo", top_k=5, max_context_chars=400)
    assert result.truncated is True
    assert result.context_chars <= 400


@pytest.mark.integration
def test_caller_access_level_hides_restricted_chunks(
    rag_config: RagConfig,
    mock_embedder: MockEmbedding,
) -> None:
    cfg_pub = replace(rag_config, default_access_level="public")
    cfg_pri = replace(rag_config, default_access_level="private")
    ing_pub = RagIngestor(cfg_pub, embed_model=mock_embedder)
    ing_pri = RagIngestor(cfg_pri, embed_model=mock_embedder)
    retriever = RagRetriever(rag_config, embed_model=mock_embedder)

    pub = _write_knowledge(cfg_pub.knowledge_dir, "pub.md", "# Pub\nconteúdo visível público")
    pri = _write_knowledge(cfg_pri.knowledge_dir, "pri.md", "# Pri\nconteúdo visível público")
    ing_pub.ingest_file(pub)
    ing_pri.ingest_file(pri)

    result = retriever.search("visível público", top_k=10, caller_access_level="public")
    levels = {hit.access_level for hit in result.hits}
    assert levels <= {"public"}
    sources = {hit.source for hit in result.hits}
    assert "pri.md" not in sources


@pytest.mark.integration
def test_search_knowledge_module_helper(
    rag_config: RagConfig,
    ingestor: RagIngestor,
    mock_embedder: MockEmbedding,
) -> None:
    doc = _write_knowledge(rag_config.knowledge_dir, "helper.md", "# T\nconsulta helper")
    ingestor.ingest_file(doc)

    result = search_knowledge(
        "consulta",
        chroma_dir=rag_config.chroma_dir,
        knowledge_dir=rag_config.knowledge_dir,
        top_k=1,
        embed_model=mock_embedder,
    )
    assert result.hits
    assert result.hits[0].title == "T"