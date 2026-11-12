"""RRF: fusão vetorial + full-text."""

from __future__ import annotations

from src.yby_seed.memory.retriever import fuse_rrf, rrf_score


def test_rrf_score_single_source() -> None:
    assert rrf_score(0, None) == 1 / 60
    assert rrf_score(None, 0) == 1 / 60


def test_fuse_rrf_prefers_overlap() -> None:
    vec_rows = [
        ("GPIO35 doc A", "esp_idf", "a.md"),
        ("semantic only", "esp_idf", "b.md"),
    ]
    fts_rows = [
        ("GPIO35 register 0x03", "esp_idf", "c.md"),
        ("GPIO35 doc A", "esp_idf", "a.md"),
    ]
    fused = fuse_rrf(vec_rows, fts_rows, top_k=3)
    contents = [row[0] for row in fused]
    assert contents[0] == "GPIO35 doc A"
    assert len(fused) == 3
