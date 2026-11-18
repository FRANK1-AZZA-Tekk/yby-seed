"""Leitura e metadados de documentos locais (data/knowledge)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from llama_index.core import Document
from llama_index.readers.file import PDFReader

from src.yby.rag.errors import UnsupportedDocumentError

DocType = Literal["md", "txt", "pdf"]
SUPPORTED_SUFFIXES = frozenset({".md", ".txt", ".pdf"})
FUTURE_SUFFIXES = frozenset({".docx"})

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_TITLE_MD = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_PDF_READER = PDFReader()


def assert_knowledge_path(path: Path, knowledge_root: Path) -> Path:
    """Garante arquivo regular dentro de knowledge_root, sem symlink de escape."""

    if path.is_symlink():
        raise UnsupportedDocumentError("symlinks não são permitidos na ingestão")

    root = knowledge_root.resolve()
    try:
        resolved = path.expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise UnsupportedDocumentError(f"arquivo inexistente: {path}") from exc

    if not resolved.is_file():
        raise UnsupportedDocumentError(f"não é um arquivo: {resolved}")

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise UnsupportedDocumentError(
            f"caminho fora de data/knowledge: {path}"
        ) from exc

    return resolved


def sha256_file(path: Path, *, max_bytes: int) -> str:
    size = path.stat().st_size
    if size > max_bytes:
        raise UnsupportedDocumentError(
            f"arquivo excede o limite de {max_bytes} bytes"
        )

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def iso_from_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def guess_language(text: str, *, default: str = "pt-BR") -> str:
    sample = text[:2000].lower()
    pt_hits = sum(
        1 for token in ("ção", " não ", " para ", " você ", " são ") if token in sample
    )
    return default if pt_hits >= 2 else "und"


def metadata_from_text(
    text: str,
    path: Path,
    default_tags: list[str] | None = None,
) -> tuple[str, list[str], str]:
    body = text
    tags = list(default_tags or [])
    title = path.stem

    match = _FRONTMATTER.match(text)
    if match:
        block = match.group(1)
        body = text[match.end() :]
        for line in block.splitlines():
            if line.lower().startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"')
            elif line.lower().startswith("tags:"):
                raw = line.split(":", 1)[1].strip()
                tags = [part.strip() for part in raw.split(",") if part.strip()]

    heading = _TITLE_MD.search(body)
    if heading and title == path.stem:
        title = heading.group(1).strip()

    language = guess_language(body)
    return title, tags, language


def tags_to_chroma(tags: list[str]) -> str:
    return json.dumps(tags, ensure_ascii=False)


def load_document(
    path: Path,
    *,
    access_level: str,
    default_tags: list[str] | None = None,
) -> Document:
    suffix = path.suffix.lower()
    if suffix in FUTURE_SUFFIXES:
        raise UnsupportedDocumentError(f"tipo reservado para futuro: {suffix}")
    if suffix not in SUPPORTED_SUFFIXES:
        raise UnsupportedDocumentError(f"tipo não suportado: {suffix}")

    doc_type: DocType = suffix.lstrip(".")  # type: ignore[assignment]
    stat = path.stat()
    created_at = iso_from_timestamp(stat.st_ctime)
    updated_at = iso_from_timestamp(stat.st_mtime)

    if suffix == ".pdf":
        pages = _PDF_READER.load_data(file=path)
        text = "\n\n".join(page.text for page in pages if page.text)
        title = path.stem
        tags = list(default_tags or [])
        language = guess_language(text)
    else:
        text = path.read_text(encoding="utf-8", errors="replace")
        title, tags, language = metadata_from_text(text, path, default_tags=default_tags)

    if not text.strip():
        raise UnsupportedDocumentError("documento vazio")

    metadata = {
        "source": str(path),
        "title": title,
        "doc_type": doc_type,
        "language": language,
        "created_at": created_at,
        "updated_at": updated_at,
        "tags": tags_to_chroma(tags),
        "access_level": access_level,
    }
    return Document(text=text, metadata=metadata)