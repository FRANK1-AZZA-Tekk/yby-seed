"""Testes unitários do RAGOptimizer (sem dependência de Ollama/LanceDB/tree-sitter reais)."""

from __future__ import annotations

import sys
from datetime import datetime
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _load_rag_optimizer(monkeypatch: pytest.MonkeyPatch):
    if "lancedb" not in sys.modules:
        ldb_mod = ModuleType("lancedb")
        ldb_mod.connect = MagicMock()  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "lancedb", ldb_mod)

    ts_mod = ModuleType("tree_sitter")
    fake_parser = MagicMock()
    fake_parser.return_value.parse.return_value = MagicMock(root_node=MagicMock(children=[]))
    ts_mod.Parser = fake_parser  # type: ignore[attr-defined]
    tsp_mod = ModuleType("tree_sitter_python")
    tsp_mod.language = lambda: object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tree_sitter", ts_mod)
    monkeypatch.setitem(sys.modules, "tree_sitter_python", tsp_mod)
    sys.modules.pop("src.rag.ast_chunker", None)
    sys.modules.pop("src.rag.rag_optimizer", None)

    from src.rag.rag_optimizer import RAGOptimizer

    return RAGOptimizer


@pytest.mark.asyncio
async def test_rag_optimizer_index_and_search_with_mocked_ollama_and_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    RAGOptimizer = _load_rag_optimizer(monkeypatch)
    with patch("src.rag.rag_optimizer.kv_cache_config.validate") as validate_mock:
        rag = RAGOptimizer(db_path="/tmp/rag-test", ollama_host="http://127.0.0.1:11434")
    validate_mock.assert_not_called()

    rag.db.insert_vector = AsyncMock()
    rag.db.search = AsyncMock(
        return_value=[
            {"text": "def somar(a, b):\n    return a + b"},
        ]
    )

    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {"embedding": [0.5] * 384}

    fake_http = AsyncMock()
    fake_http.__aenter__.return_value = fake_http
    fake_http.__aexit__.return_value = False
    fake_http.post.return_value = fake_response

    with (
        patch("src.rag.rag_optimizer.httpx.AsyncClient", return_value=fake_http),
        patch(
            "src.rag.rag_optimizer.ast_chunker.chunk",
            return_value=[{"code": "def somar(a, b):\n    return a + b", "tokens": 10}],
        ),
    ):
        await rag.index_document("def somar(a, b):\n    return a + b\n", "doc1", {"author": "yby"})
        rag.db.insert_vector.assert_awaited()
        inserted = rag.db.insert_vector.await_args.args[0]
        assert inserted["timestamp"] != "2026-10-08T05:20:00Z"
        datetime.fromisoformat(inserted["timestamp"])
        assert len(inserted["vector"]) == 384

        results = await rag.search("somar", top_k=3, max_context_tokens=500)
        assert len(results) == 1
        assert "somar" in results[0]


@pytest.mark.asyncio
async def test_rag_optimizer_embedding_rejects_invalid_ollama_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    RAGOptimizer = _load_rag_optimizer(monkeypatch)
    rag = RAGOptimizer(db_path="/tmp/rag-test", ollama_host="http://127.0.0.1:11434")
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {"embedding": []}

    fake_http = AsyncMock()
    fake_http.__aenter__.return_value = fake_http
    fake_http.__aexit__.return_value = False
    fake_http.post.return_value = fake_response

    with patch("src.rag.rag_optimizer.httpx.AsyncClient", return_value=fake_http):
        with pytest.raises(RuntimeError, match="embedding"):
            await rag._generate_embedding("consulta")
