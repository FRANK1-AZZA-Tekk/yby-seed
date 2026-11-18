"""Testes do agente mínimo YBY."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("llama_index")
pytest.importorskip("chromadb")

from llama_index.core.embeddings import MockEmbedding

from src.yby.agent.loop import (
    MAX_ITERATIONS,
    MAX_TOOL_CALLS,
    ScriptedYbyPlanner,
    YbyAgentLoop,
)
from src.yby.rag.ingest import RagIngestor
from src.yby.rag.retrieve import RagRetriever
from src.yby.tools.registry import create_default_registry


@pytest.fixture
def mock_embedder() -> MockEmbedding:
    return MockEmbedding(embed_dim=64)


def test_limits_constants() -> None:
    assert MAX_ITERATIONS == 5
    assert MAX_TOOL_CALLS == 3


@pytest.mark.integration
def test_agent_uses_rag_and_returns_sources(
    tmp_path: Path,
    mock_embedder: MockEmbedding,
) -> None:
    read_root = tmp_path / "allowed"
    read_root.mkdir()
    chroma_dir = tmp_path / "chroma"
    doc = read_root / "decisions.md"
    doc.write_text("# D4\nModelo local qwen2.5-coder:3b\n", encoding="utf-8")

    ingestor = RagIngestor(chroma_dir=chroma_dir, embed_model=mock_embedder)
    ingestor.ingest_file(doc)

    registry = create_default_registry(
        read_roots=[read_root],
        rag_retriever=RagRetriever(chroma_dir=chroma_dir, embed_model=mock_embedder),
    )

    planner = ScriptedYbyPlanner(
        [
            {
                "action": "tool",
                "name": "search_knowledge",
                "arguments": {"query": "modelo local", "top_k": 2},
                "justification": "pergunta sobre decisões do projeto",
            },
            {
                "action": "finish",
                "answer": {
                    "text": "O modelo local é o qwen2.5-coder:3b (D4).",
                    "sources": [],
                },
            },
        ]
    )

    log_path = tmp_path / "runs.jsonl"
    loop = YbyAgentLoop(
        registry=registry,
        planner=planner,
        log_path=log_path,
    )
    result = loop.run("Qual modelo local o projeto usa?")

    assert result.status == "completed"
    assert result.tools_used == ["search_knowledge"]
    assert result.sources
    assert any("qwen" in (src.get("excerpt") or "").lower() for src in result.sources)
    assert result.answer is not None
    assert "sources" in result.answer
    assert len(result.answer["sources"]) >= 1
    assert result.structured_action is not None
    assert result.structured_action["action"] == "tool"
    assert result.telemetry["provider"] == "ollama_local"
    assert result.telemetry["estimated_cost_usd"] == 0.0
    assert "search_knowledge" in result.telemetry["tools_used"]
    assert log_path.is_file()
    logged = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert logged["event"] == "agent_run"
    assert logged["status"] == "completed"


def test_agent_blocks_fourth_tool(tmp_path: Path, mock_embedder: MockEmbedding) -> None:
    read_root = tmp_path / "allowed"
    read_root.mkdir()
    registry = create_default_registry(
        read_roots=[read_root],
        rag_retriever=RagRetriever(chroma_dir=tmp_path / "c", embed_model=mock_embedder),
    )
    steps = []
    for _ in range(4):
        steps.append(
            {
                "action": "tool",
                "name": "list_files",
                "arguments": {"path": str(read_root)},
                "justification": "teste",
            }
        )
    planner = ScriptedYbyPlanner(steps)
    loop = YbyAgentLoop(registry=registry, planner=planner, log_path=tmp_path / "log.jsonl")
    result = loop.run("listar")

    assert result.status == "max_tools"
    assert len(result.tools_used) == MAX_TOOL_CALLS
    assert result.structured_action is not None


def test_agent_empty_question(tmp_path: Path, mock_embedder: MockEmbedding) -> None:
    registry = create_default_registry(
        read_roots=[tmp_path],
        rag_retriever=RagRetriever(chroma_dir=tmp_path / "c", embed_model=mock_embedder),
    )
    loop = YbyAgentLoop(
        registry=registry,
        planner=ScriptedYbyPlanner([]),
        log_path=tmp_path / "unused.jsonl",
    )
    result = loop.run("   ")
    assert result.status == "error"