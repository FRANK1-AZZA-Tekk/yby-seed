"""Repo-map (Aider) e patches SEARCH/REPLACE."""

from __future__ import annotations

from pathlib import Path

from src.yby_seed.agents.surgical_patch import (
    apply_search_replace_blocks,
    parse_search_replace_blocks,
)
from src.yby_seed.mcp.repo_map import build_repo_map


def test_build_repo_map_python_and_cpp(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "class Greeter:\n    def hello(self, name: str) -> str:\n        return name\n",
        encoding="utf-8",
    )
    (tmp_path / "main.cpp").write_text(
        "#define LED_PIN 5\nstruct Sensor { int id; };\nvoid init() { }\n",
        encoding="utf-8",
    )
    payload = build_repo_map(tmp_path)
    assert payload["file_count"] == 2
    py_file = next(f for f in payload["files"] if f["file"] == "app.py")
    assert any(s["name"] == "Greeter" for s in py_file["symbols"])
    cpp_file = next(f for f in payload["files"] if f["file"] == "main.cpp")
    names = {s["name"] for s in cpp_file["symbols"]}
    assert "Sensor" in names
    assert "LED_PIN" in names


def test_surgical_patch_apply_and_fallback() -> None:
    original = "def add(a, b):\n    return a - b\n"
    blocks_text = """<<<<<<< SEARCH
    return a - b
=======
    return a + b
>>>>>>> REPLACE
"""
    blocks = parse_search_replace_blocks(blocks_text)
    assert len(blocks) == 1
    patched, applied, errors = apply_search_replace_blocks(original, blocks)
    assert applied == 1
    assert not errors
    assert "a + b" in patched

    missing, applied2, errors2 = apply_search_replace_blocks(original, [("nope", "x")])
    assert applied2 == 0
    assert errors2
    assert missing == original
