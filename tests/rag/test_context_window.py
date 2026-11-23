"""Janela deslizante e cache RAG (sem embeddings reais)."""

from __future__ import annotations

import time

from src.rag.context_window import RankedSnippet, estimate_tokens, join_snippets, sliding_context_window
from src.rag.search_cache import RagCaches, cache_key


def test_estimate_tokens() -> None:
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 80) == 20


def test_sliding_context_prioriza_relevancia_e_limite() -> None:
    snippets = [
        RankedSnippet("A" * 40, score=0.2, timestamp=1.0),
        RankedSnippet("B" * 40, score=0.9, timestamp=2.0),
        RankedSnippet("C" * 40, score=0.8, timestamp=3.0),
    ]
    picked = sliding_context_window(snippets, max_tokens=25)
    assert len(picked) == 2
    assert picked[0].timestamp <= picked[-1].timestamp
    assert "B" in join_snippets(picked)


def test_rag_caches_embedding_e_busca() -> None:
    caches = RagCaches()
    now = time.time()
    key_emb = cache_key("emb", "query")
    key_search = cache_key("search", "query", 3)
    caches.embedding.set(key_emb, [0.1, 0.2], now=now)
    caches.search.set(key_search, [{"id": 1}], now=now)
    assert caches.embedding.get(key_emb, now=now) == [0.1, 0.2]
    assert caches.search.get(key_search, now=now) == [{"id": 1}]
    assert caches.embedding.get(key_emb, now=now + 601) is None