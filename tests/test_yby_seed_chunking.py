from src.yby_seed.memory.chunking import iter_semantic_chunks


def test_preserves_code_fence_block() -> None:
    text = "Intro\n\n```python\nprint('ok')\n```\n\nFim"
    chunks = list(iter_semantic_chunks(text, max_chars=50))
    assert any("```python" in chunk for chunk in chunks)
    assert any("print('ok')" in chunk for chunk in chunks)
