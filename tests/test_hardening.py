"""Testes de robustez e segurança do núcleo YBY."""

from pathlib import Path

import pytest

from src.core.memory import MemoryStore
from src.core.rag import build_index
from src.core.skills import run_skill


def test_memory_store_ignores_invalid_jsonl(tmp_path: Path):
    memory_path = tmp_path / "memory.jsonl"
    memory_path.write_text(
        '{"question": "ok", "answer": "sim", "created_at": "2026-01-01T00:00:00Z"}\n'
        "linha invalida\n",
        encoding="utf-8",
    )
    memory = MemoryStore(memory_path)
    assert len(memory.list()) == 1


def test_rag_skips_unreadable_files(tmp_path: Path):
    bad = tmp_path / "bad.md"
    bad.write_bytes(b"\xff\xfe\xff")
    good = tmp_path / "good.md"
    good.write_text("YBY usa arquitetura local-first.", encoding="utf-8")
    chunks = build_index([tmp_path])
    assert len(chunks) == 1
    assert "local-first" in chunks[0].text


def test_read_doc_blocks_path_traversal():
    with pytest.raises(ValueError):
        run_skill("read_doc", {"name": "../secrets"})


def test_read_doc_blocks_absolute_path():
    with pytest.raises(ValueError):
        run_skill("read_doc", {"name": "/etc/passwd"})


def test_write_note_requires_confirmation(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(PermissionError):
        run_skill("write_note", {"title": "teste", "content": "olá"})


def test_write_note_with_confirmation(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = run_skill(
        "write_note",
        {"title": "teste", "content": "olá"},
        confirm=True,
    )
    assert "Nota salva" in result
    assert (tmp_path / ".yby/notes/teste.md").read_text(encoding="utf-8") == "olá"
