"""Ferramentas list_files e read_file (somente leitura allowlisted)."""

from __future__ import annotations

import fnmatch
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.yby.tools.schemas import FileEntryOut, ListFilesArgs, ListFilesOutput, ReadFileArgs, ReadFileOutput
from src.yby.tools.security import (
    SAFE_READ_EXTENSIONS,
    assert_allowed_path,
    assert_safe_extension,
    assert_safe_file_name,
    looks_binary,
    relative_to_root,
)


def list_files_handler(roots: list[Path]) -> Callable[[BaseModel], dict[str, Any]]:
    def handler(args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, ListFilesArgs)
        directory = assert_allowed_path(args.directory, roots=roots)
        if not directory.is_dir():
            raise ValueError("directory não é um diretório")

        entries: list[FileEntryOut] = []
        for child in sorted(directory.iterdir()):
            if child.is_symlink():
                continue
            if child.is_dir():
                continue
            if child.suffix.lower() not in SAFE_READ_EXTENSIONS:
                continue
            if not fnmatch.fnmatch(child.name, args.pattern):
                continue
            try:
                assert_safe_file_name(child.name)
            except Exception:
                continue
            size = child.stat().st_size
            entries.append(
                FileEntryOut(
                    path=relative_to_root(child, roots=roots),
                    name=child.name,
                    size_bytes=size,
                    extension=child.suffix.lower(),
                )
            )
            if len(entries) >= args.max_entries:
                break

        out = ListFilesOutput(
            directory=relative_to_root(directory, roots=roots),
            entries=entries,
            truncated=len(entries) >= args.max_entries,
        )
        return out.model_dump()

    return handler


def read_file_handler(roots: list[Path]) -> Callable[[BaseModel], dict[str, Any]]:
    def handler(args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, ReadFileArgs)
        file_path = assert_allowed_path(args.path, roots=roots)
        if file_path.is_symlink():
            raise ValueError("symlink não permitido")
        if not file_path.is_file():
            raise FileNotFoundError(f"arquivo inexistente: {args.path}")

        assert_safe_file_name(file_path.name)
        assert_safe_extension(file_path)

        size = file_path.stat().st_size
        with file_path.open("rb") as handle:
            raw = handle.read(args.max_bytes)

        if looks_binary(raw):
            raise ValueError("conteúdo parece binário; leitura bloqueada")

        truncated = size > len(raw)
        text = raw.decode(args.encoding, errors="strict")

        out = ReadFileOutput(
            path=relative_to_root(file_path, roots=roots),
            size_bytes=size,
            read_bytes=len(raw),
            truncated=truncated,
            encoding=args.encoding,
            content=text,
        )
        return out.model_dump()

    return handler