"""RAG local mínimo baseado em palavras-chave e arquivos Markdown."""

from dataclasses import dataclass
from pathlib import Path

from loguru import logger


@dataclass(frozen=True)
class Chunk:
    text: str
    source: str
    line: int


def _tokenize(text: str) -> set[str]:
    return {word.lower() for word in text.split() if len(word) > 2}


def _iter_markdown_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        resolved_root = root.resolve()
        if root.is_file() and root.suffix == ".md":
            files.append(root)
        elif root.is_dir():
            for path in sorted(root.rglob("*.md")):
                try:
                    path.resolve().relative_to(resolved_root)
                    files.append(path)
                except ValueError:
                    logger.warning(f"Ignorando arquivo fora da raiz permitida: {path}")
    return files


def build_index(roots: list[Path] | None = None) -> list[Chunk]:
    """Indexa documentos Markdown locais em blocos por parágrafo."""
    roots = roots or [Path("docs"), Path("README.md")]
    chunks: list[Chunk] = []
    for path in _iter_markdown_files(roots):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            logger.warning(f"Ignorando documento ilegível {path}: {exc}")
            continue
        buffer: list[str] = []
        start = 1
        for number, line in enumerate(lines, start=1):
            if line.strip():
                if not buffer:
                    start = number
                buffer.append(line)
            elif buffer:
                chunks.append(Chunk(text="\n".join(buffer), source=str(path), line=start))
                buffer = []
        if buffer:
            chunks.append(Chunk(text="\n".join(buffer), source=str(path), line=start))
    return chunks


def search(question: str, chunks: list[Chunk], limit: int = 3) -> list[Chunk]:
    """Busca os blocos mais relevantes por interseção de palavras-chave."""
    query = _tokenize(question)
    scored: list[tuple[int, Chunk]] = []
    for chunk in chunks:
        overlap = len(query & _tokenize(chunk.text))
        if overlap:
            scored.append((overlap, chunk))
    scored.sort(key=lambda item: (-item[0], item[1].source, item[1].line))
    return [chunk for _, chunk in scored[:limit]]


def format_citations(chunks: list[Chunk]) -> str:
    return "\n".join(f"- {chunk.source}:{chunk.line}" for chunk in chunks)
