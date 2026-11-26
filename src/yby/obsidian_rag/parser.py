"""Parser leve de Obsidian Flavored Markdown (YAML frontmatter, wikilinks e chunking)."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

_FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(.*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|\Z)",
    re.DOTALL,
)
_FENCED_CODE_RE = re.compile(
    r"(^```[^\n]*\n.*?^```[ \t]*$|^~~~[^\n]*\n.*?^~~~[ \t]*$)",
    re.MULTILINE | re.DOTALL,
)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_EMBED_RE = re.compile(r"!\[\[([^\[\]]+)\]\]")
_WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\[\]]+)\]\]")
_INLINE_TAG_RE = re.compile(r"(?<![\w/&#])#([A-Za-zÀ-ÿ][A-Za-z0-9À-ÿ/_-]*)")
_HEX_COLOR_RE = re.compile(r"^[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{5})?$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


class ParsedObsidianNote(BaseModel):
    """Representação estruturada de uma nota Markdown do cofre Obsidian."""

    model_config = ConfigDict(extra="forbid")

    source_path: str
    title: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body: str = ""
    wikilinks: list[str] = Field(default_factory=list)
    embeds: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    content_hash: str


class ObsidianChunk(BaseModel):
    """Chunk semântico com metadados Obsidian pronto para busca híbrida / pgvector."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    source_path: str
    chunk_index: int
    heading: str = ""
    content: str
    content_hash: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    wikilinks: list[str] = Field(default_factory=list)
    embeds: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    token_estimate: int = 0


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _normalize_wikilink_target(raw: str) -> str:
    # Remove alias (`target|alias`) e âncora (`target#heading`) mantendo o alvo canônico.
    without_alias = raw.split("|", 1)[0].strip()
    target = without_alias.split("#", 1)[0].strip()
    return target or without_alias


def _strip_code_for_metadata(text: str) -> str:
    no_fenced = _FENCED_CODE_RE.sub("\n", text)
    return _INLINE_CODE_RE.sub(" ", no_fenced)


def _extract_links_and_tags(
    text: str,
    frontmatter: dict[str, Any] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    clean = _strip_code_for_metadata(text)

    embeds = [_normalize_wikilink_target(m.group(1)) for m in _EMBED_RE.finditer(clean)]
    wikilinks = [_normalize_wikilink_target(m.group(1)) for m in _WIKILINK_RE.finditer(clean)]

    raw_tags: list[str] = []
    if frontmatter:
        fm_tags = frontmatter.get("tags")
        if isinstance(fm_tags, str):
            raw_tags.extend(part.strip().lstrip("#") for part in re.split(r"[,\s]+", fm_tags))
        elif isinstance(fm_tags, list):
            for entry in fm_tags:
                if isinstance(entry, str):
                    raw_tags.append(entry.strip().lstrip("#"))

        # Coleta wikilinks eventualmente declarados em propriedades YAML.
        for val in frontmatter.values():
            if isinstance(val, str):
                wikilinks.extend(
                    _normalize_wikilink_target(m.group(1)) for m in _WIKILINK_RE.finditer(val)
                )
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        wikilinks.extend(
                            _normalize_wikilink_target(m.group(1))
                            for m in _WIKILINK_RE.finditer(item)
                        )

    for match in _INLINE_TAG_RE.finditer(clean):
        candidate = match.group(1).strip()
        if _HEX_COLOR_RE.match(candidate):
            continue
        raw_tags.append(candidate)

    return (
        _dedupe_preserve(wikilinks),
        _dedupe_preserve(embeds),
        _dedupe_preserve([t.casefold() for t in raw_tags if t]),
    )


def _extract_title(source_path: str, frontmatter: dict[str, Any], body: str) -> str:
    fm_title = frontmatter.get("title")
    if isinstance(fm_title, str) and fm_title.strip():
        return fm_title.strip()
    for line in body.splitlines():
        match = _HEADING_RE.match(line)
        if match and len(match.group(1)) == 1:
            return match.group(2).strip()
    stem = source_path.rsplit("/", 1)[-1]
    return stem[:-3] if stem.endswith(".md") else stem


def parse_obsidian_markdown(text: str, source_path: str = "note.md") -> ParsedObsidianNote:
    """Extrai frontmatter YAML, wikilinks, embeds e tags de uma nota Obsidian."""

    raw = (text or "").lstrip("\ufeff")
    content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    frontmatter: dict[str, Any] = {}
    body = raw

    match = _FRONTMATTER_RE.match(raw)
    if match:
        yaml_block = match.group(1)
        body = raw[match.end() :]
        try:
            parsed = yaml.safe_load(yaml_block)
            if isinstance(parsed, dict):
                frontmatter = _json_safe(parsed)
        except yaml.YAMLError:
            frontmatter = {}

    wikilinks, embeds, tags = _extract_links_and_tags(body, frontmatter=frontmatter)
    title = _extract_title(source_path, frontmatter, body)

    return ParsedObsidianNote(
        source_path=source_path,
        title=title,
        frontmatter=frontmatter,
        body=body.strip(),
        wikilinks=wikilinks,
        embeds=embeds,
        tags=tags,
        content_hash=content_hash,
    )


def _split_sections(body: str, default_heading: str) -> list[tuple[str, str]]:
    """Divide o corpo Markdown por headings preservando blocos de código cercados."""

    sections: list[tuple[str, str]] = []
    current_heading = default_heading
    buffer: list[str] = []
    in_fence = False
    fence_marker = ""

    for line in body.splitlines():
        stripped = line.lstrip()
        if not in_fence and (stripped.startswith("```") or stripped.startswith("~~~")):
            in_fence = True
            fence_marker = stripped[:3]
            buffer.append(line)
            continue
        if in_fence:
            buffer.append(line)
            if stripped.startswith(fence_marker):
                in_fence = False
                fence_marker = ""
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            if buffer and "\n".join(buffer).strip():
                sections.append((current_heading, "\n".join(buffer).strip()))
            current_heading = heading_match.group(2).strip()
            buffer = [line]
        else:
            buffer.append(line)

    if buffer and "\n".join(buffer).strip():
        sections.append((current_heading, "\n".join(buffer).strip()))

    return sections


def _split_oversized_text(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    step = max(1, max_chars - max(0, min(overlap, max_chars // 2)))
    pieces: list[str] = []
    start = 0
    total = len(text)

    while start < total:
        end = min(total, start + max_chars)
        if end < total:
            # Tenta quebrar em fronteira de parágrafo ou linha.
            boundary = text.rfind("\n\n", start + step // 2, end)
            if boundary == -1:
                boundary = text.rfind("\n", start + step // 2, end)
            if boundary == -1:
                boundary = text.rfind(" ", start + step // 2, end)
            if boundary != -1 and boundary > start:
                end = boundary
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= total:
            break
        start = max(start + 1, end - overlap)

    return pieces


def chunk_obsidian_document(
    doc: ParsedObsidianNote,
    *,
    max_chars: int = 900,
    overlap: int = 120,
) -> list[ObsidianChunk]:
    """Segmenta uma `ParsedObsidianNote` em chunks enriquecidos com metadados."""

    if max_chars < 100:
        raise ValueError("max_chars deve ser >= 100")

    sections = _split_sections(doc.body, doc.title) if doc.body else []
    if not sections and doc.frontmatter:
        meta_lines = [f"{k}: {v}" for k, v in doc.frontmatter.items()]
        sections = [(doc.title, "\n".join(meta_lines))]

    chunks: list[ObsidianChunk] = []
    chunk_idx = 0

    for heading, section_text in sections:
        for piece in _split_oversized_text(section_text, max_chars=max_chars, overlap=overlap):
            local_links, local_embeds, local_tags = _extract_links_and_tags(
                piece,
                frontmatter=doc.frontmatter,
            )
            merged_links = _dedupe_preserve(local_links or list(doc.wikilinks))
            merged_embeds = _dedupe_preserve(local_embeds)
            merged_tags = _dedupe_preserve(local_tags)
            piece_hash = hashlib.sha256(piece.encode("utf-8")).hexdigest()
            chunk_id = hashlib.sha256(
                f"{doc.source_path}:{chunk_idx}:{piece_hash}".encode("utf-8")
            ).hexdigest()[:24]

            chunks.append(
                ObsidianChunk(
                    chunk_id=chunk_id,
                    source_path=doc.source_path,
                    chunk_index=chunk_idx,
                    heading=heading,
                    content=piece,
                    content_hash=piece_hash,
                    frontmatter=doc.frontmatter,
                    wikilinks=merged_links,
                    embeds=merged_embeds,
                    tags=merged_tags,
                    token_estimate=max(1, len(piece.split())),
                )
            )
            chunk_idx += 1

    return chunks
