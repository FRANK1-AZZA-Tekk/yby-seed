"""Chunking semântico preservando blocos ``` intactos."""

from __future__ import annotations

import re
from typing import Iterator

_FENCE_RE = re.compile(r"^```[\w+-]*\s*$", re.MULTILINE)


def iter_semantic_chunks(text: str, max_chars: int = 1800) -> Iterator[str]:
    """Quebra texto em chunks respeitando cercas de código."""
    parts: list[str] = []
    last = 0
    in_fence = False
    for match in _FENCE_RE.finditer(text):
        if not in_fence:
            parts.append(text[last : match.start()])
            in_fence = True
            last = match.start()
        else:
            parts.append(text[last : match.end()])
            in_fence = False
            last = match.end()
    parts.append(text[last:])

    buffer = ""
    for part in parts:
        stripped = part.strip()
        if not stripped:
            continue
        is_code = stripped.startswith("```")
        if is_code:
            if buffer.strip():
                yield buffer.strip()
                buffer = ""
            yield stripped
            continue
        if len(buffer) + len(part) <= max_chars:
            buffer += part
        else:
            if buffer.strip():
                yield buffer.strip()
            buffer = part
    if buffer.strip():
        yield buffer.strip()
