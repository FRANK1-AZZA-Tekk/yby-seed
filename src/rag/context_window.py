"""Janela deslizante de contexto para RAG (sem LLM, VRAM 0)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankedSnippet:
    """Trecho candidato ao contexto do LLM."""

    text: str
    score: float
    timestamp: float


def estimate_tokens(text: str) -> int:
    """Heurística leve (~4 chars/token), alinhada a D12."""

    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, len(stripped) // 4)


def sliding_context_window(
    snippets: list[RankedSnippet],
    max_tokens: int,
) -> list[RankedSnippet]:
    """
    Seleciona trechos por relevância e recência, respeitando ``max_tokens``.

    Retorna em ordem cronológica (timestamp crescente) para o prompt.
    """
    if max_tokens <= 0 or not snippets:
        return []
    ranked = sorted(
        snippets,
        key=lambda item: (item.score, item.timestamp),
        reverse=True,
    )
    chosen: list[RankedSnippet] = []
    used = 0
    for item in ranked:
        need = estimate_tokens(item.text)
        if used + need > max_tokens:
            continue
        chosen.append(item)
        used += need
    chosen.sort(key=lambda item: item.timestamp)
    return chosen


def join_snippets(snippets: list[RankedSnippet]) -> str:
    """Concatena trechos para injeção no prompt."""

    return "\n\n".join(s.text for s in snippets if s.text.strip())