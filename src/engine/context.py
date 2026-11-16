"""Limite de contexto antes de enviar para a nuvem."""

from __future__ import annotations

TRUNCATION_MARKER = "\n…[contexto truncado]…\n"


def trim_context(text: str, max_chars: int) -> str:
    """Corta o texto ao orçamento. `max_chars` <= 0 = sem corte."""

    if max_chars <= 0 or len(text) <= max_chars:
        return text
    marker = TRUNCATION_MARKER
    if max_chars <= len(marker):
        return text[:max_chars]
    keep = max_chars - len(marker)
    head = keep * 2 // 3
    tail = keep - head
    return text[:head] + marker + text[-tail:]
