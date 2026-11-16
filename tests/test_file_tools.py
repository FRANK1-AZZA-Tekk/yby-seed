"""Testes de list_files e read_file."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.yby.tools.registry import create_default_registry


@pytest.fixture
def read_root(tmp_path: Path) -> Path:
    root = tmp_path / "allowed"
    root.mkdir()
    return root


@pytest.fixture
def registry(read_root: Path):
    return create_default_registry(read_roots=[read_root])


def test_list_files_relative_paths_and_pattern(registry, read_root: Path) -> None:
    (read_root / "keep.md").write_text("# k", encoding="utf-8")
    (read_root / "skip.bin").write_bytes(b"\x00")
    (read_root / "data.json").write_text("{}", encoding="utf-8")

    response = registry.run(
        "list_files",
        {"directory": ".", "pattern": "*.md"},
    )
    assert response.ok is True
    assert response.data is not None
    assert len(response.data["entries"]) == 1
    entry = response.data["entries"][0]
    assert entry["name"] == "keep.md"
    assert entry["extension"] == ".md"
    assert entry["path"] == "keep.md"
    assert read_root.as_posix() not in entry["path"]


def test_read_file_truncates_and_relative_path(registry, read_root: Path) -> None:
    target = read_root / "a.txt"
    target.write_text("abcdefghij", encoding="utf-8")
    response = registry.run("read_file", {"path": "a.txt", "max_bytes": 4})
    assert response.ok is True
    assert response.data is not None
    assert response.data["path"] == "a.txt"
    assert response.data["truncated"] is True
    assert response.data["content"] == "abcd"


def test_read_file_rejects_outside_allowlist(registry, tmp_path: Path) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_text("x", encoding="utf-8")
    response = registry.run("read_file", {"path": str(outside)})
    assert response.ok is False
    assert response.error is not None
    assert response.error.code in {"path_not_allowed", "unsafe_path"}


def test_path_traversal_blocked(registry) -> None:
    response = registry.run("read_file", {"path": "../etc/passwd"})
    assert response.ok is False
    assert response.error is not None
    assert response.error.code in {"validation_error", "unsafe_path", "path_not_allowed"}


def test_unsafe_extension_blocked(registry, read_root: Path) -> None:
    (read_root / "malware.exe").write_bytes(b"MZ")
    response = registry.run("read_file", {"path": "malware.exe"})
    assert response.ok is False
    assert response.error is not None
    assert response.error.code in {"unsafe_path", "execution_error"}


def test_binary_content_blocked(registry, read_root: Path) -> None:
    (read_root / "fake.txt").write_bytes(b"\x00\x01\x02")
    response = registry.run("read_file", {"path": "fake.txt"})
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "execution_error"


def test_symlink_rejected(registry, read_root: Path) -> None:
    real = read_root / "real.md"
    real.write_text("# x", encoding="utf-8")
    link = read_root / "link.md"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlink não suportado neste ambiente")
    response = registry.run("read_file", {"path": "link.md"})
    assert response.ok is False
    assert response.error is not None
    assert response.error.code in {"unsafe_path", "execution_error"}


def test_sensitive_env_file_blocked(registry, read_root: Path) -> None:
    (read_root / ".env").write_text("SECRET=1", encoding="utf-8")
    response = registry.run("read_file", {"path": ".env"})
    assert response.ok is False
    assert response.error is not None
    assert response.error.code in {"unsafe_path", "execution_error"}