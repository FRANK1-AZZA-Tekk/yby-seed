"""Aplicação de patches cirúrgicos estilo SEARCH/REPLACE (padrão Aider)."""

from __future__ import annotations

import re

SEARCH_MARKER = "<<<<<<< SEARCH"
MID_MARKER = "======="
REPLACE_MARKER = ">>>>>>> REPLACE"

_BLOCK_RE = re.compile(
    rf"{re.escape(SEARCH_MARKER)}\s*\n(.*?)\n{re.escape(MID_MARKER)}\s*\n(.*?)\n{re.escape(REPLACE_MARKER)}",
    re.DOTALL,
)


def parse_search_replace_blocks(text: str) -> list[tuple[str, str]]:
    """Extrai pares (search, replace) de blocos no texto."""
    blocks: list[tuple[str, str]] = []
    for match in _BLOCK_RE.finditer(text):
        search = match.group(1)
        replace = match.group(2)
        if search:
            blocks.append((search, replace))
    return blocks


def apply_search_replace_blocks(
    code: str,
    blocks: list[tuple[str, str]],
) -> tuple[str, int, list[str]]:
    """Aplica blocos em ordem; retorna (código, aplicados, erros)."""
    result = code
    applied = 0
    errors: list[str] = []
    for idx, (search, replace) in enumerate(blocks, start=1):
        if search not in result:
            preview = search[:48].replace("\n", "\\n")
            errors.append(f"bloco {idx}: trecho não encontrado ({preview!r}…)")
            continue
        result = result.replace(search, replace, 1)
        applied += 1
    return result, applied, errors
