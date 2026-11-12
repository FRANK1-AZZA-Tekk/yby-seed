"""RAG — chunking e contratos offline (sem embeddings reais)."""

from src.yby_seed.memory.chunking import iter_semantic_chunks


def test_rag_chunking_preserves_code_fence_block() -> None:
    text = "Intro\n\n```python\nprint('ok')\n```\n\nFim."
    chunks = list(iter_semantic_chunks(text))
    assert any(c.startswith("```") for c in chunks)
    assert any("Intro" in c for c in chunks)


def test_rag_chunking_preserves_short_document() -> None:
    text = "documento único"
    chunks = list(iter_semantic_chunks(text))
    assert chunks == ["documento único"]
