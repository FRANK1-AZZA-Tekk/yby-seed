"""Testes do loop do agente YBY (Tarefa 5)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("llama_index")
pytest.importorskip("chromadb")

from llama_index.core.embeddings import MockEmbedding

from src.yby.agent.loop import (
    FailingPlanner,
    MAX_ITERATIONS,
    MAX_TOOL_CALLS,
    ScriptedYbyPlanner,
    YbyAgentLoop,
)
from src.yby.rag.config import RagConfig
from src.yby.rag.ingest import RagIngestor
from src.yby.rag.retrieve import RagRetriever
from src.yby.tools.registry import create_default_registry

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "documents"


@pytest.fixture
def mock_embedder() -> MockEmbedding:
    return MockEmbedding(embed_dim=64)


@pytest.fixture
def rag_stack(tmp_path: Path, mock_embedder: MockEmbedding):
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


def test_limits_constants() -> None:
    assert MAX_ITERATIONS == 5
    assert MAX_TOOL_CALLS == 3


@pytest.mark.integration
def test_agent_uses_rag_and_returns_sources(
    rag_stack,
    tmp_path: Path,
) -> None:
    cfg, ingestor, retriever = rag_stack
    shutil.copy(FIXTURES / "sample.md", cfg.knowledge_dir / "sample.md")
    ingestor.ingest_file(cfg.knowledge_dir / "sample.md")

    registry = create_default_registry(
        read_roots=[cfg.knowledge_dir],
        rag_retriever=retriever,
    )

    planner = ScriptedYbyPlanner(
        [
            {
                "action": "tool",
                "name": "search_knowledge",
                "arguments": {"query": "ingestão português", "top_k": 2},
                "justification": "pergunta sobre documentação",
            },
            {
                "action": "finish",
                "answer": {
                    "text": "Há documentação de teste no índice.",
                    "sources": [],
                    "confidence": "high",
                    "needs_approval": False,
                    "warnings": [],
                },
            },
        ]
    )

    log_path = tmp_path / "runs.jsonl"
    loop = YbyAgentLoop(registry=registry, planner=planner, log_path=log_path)
    result = loop.run("O que está no índice de teste?")

    assert result.status == "completed"
    assert "search_knowledge" in result.tools_used
    assert result.sources
    assert result.structured is not None
    assert result.structured.sources
    assert result.structured.trace_id
    assert result.structured.latency_ms >= 0
    assert result.structured.confidence == "high"
    assert log_path.is_file()
    logged = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert logged["event"] == "agent_run"
    assert logged["trace_id"] == result.trace_id


def test_agent_blocks_fourth_tool(tmp_path: Path, mock_embedder: MockEmbedding) -> None:
    read_root = tmp_path / "allowed"
    read_root.mkdir()
    registry = create_default_registry(
        read_roots=[read_root],
        rag_retriever=RagRetriever(chroma_dir=tmp_path / "c", embed_model=mock_embedder),
    )
    steps = [
        {
            "action": "tool",
            "name": "list_files",
            "arguments": {"directory": "."},
            "justification": "teste",
        }
        for _ in range(4)
    ]
    planner = ScriptedYbyPlanner(steps)
    loop = YbyAgentLoop(registry=registry, planner=planner, log_path=tmp_path / "log.jsonl")
    result = loop.run("listar")

    assert result.status == "max_tools"
    assert len(result.tools_used) == MAX_TOOL_CALLS


def test_agent_max_iterations(tmp_path: Path, mock_embedder: MockEmbedding) -> None:
    read_root = tmp_path / "allowed"
    read_root.mkdir()
    registry = create_default_registry(
        read_roots=[read_root],
        rag_retriever=RagRetriever(chroma_dir=tmp_path / "c", embed_model=mock_embedder),
    )
    steps = [
        {
            "action": "tool",
            "name": "list_files",
            "arguments": {"directory": "."},
            "justification": "loop",
        },
        {
            "action": "tool",
            "name": "list_files",
            "arguments": {"directory": "."},
            "justification": "loop",
        },
    ]
    loop = YbyAgentLoop(
        registry=registry,
        planner=ScriptedYbyPlanner(steps),
        log_path=tmp_path / "it.jsonl",
        max_iterations=2,
    )
    result = loop.run("iterar")
    assert result.status == "max_steps"
    assert len(result.tools_used) == 2


def test_unregistered_tool_rejected(tmp_path: Path, mock_embedder: MockEmbedding) -> None:
    registry = create_default_registry(
        read_roots=[tmp_path],
        rag_retriever=RagRetriever(chroma_dir=tmp_path / "c", embed_model=mock_embedder),
    )
    planner = ScriptedYbyPlanner(
        [
            {
                "action": "tool",
                "name": "run_python",
                "arguments": {},
                "justification": "malicioso",
            },
        ]
    )
    loop = YbyAgentLoop(registry=registry, planner=planner, log_path=tmp_path / "bad.jsonl")
    result = loop.run("hackear")

    assert result.status == "error"
    assert result.structured is not None
    assert "run_python" not in result.tools_used


def test_ollama_failure_structured(tmp_path: Path, mock_embedder: MockEmbedding) -> None:
    registry = create_default_registry(
        read_roots=[tmp_path],
        rag_retriever=RagRetriever(chroma_dir=tmp_path / "c", embed_model=mock_embedder),
    )
    loop = YbyAgentLoop(
        registry=registry,
        planner=FailingPlanner(),
        log_path=tmp_path / "ollama.jsonl",
    )
    result = loop.run("pergunta")
    assert result.status == "error"
    assert result.structured is not None
    assert result.structured.trace_id
    assert "Ollama" in result.structured.answer