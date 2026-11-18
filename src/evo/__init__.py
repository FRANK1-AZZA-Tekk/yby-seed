"""Evo v0.1 — observabilidade local (relatórios apenas; sem aplicar código).

Compatível com o desenho em `docs/future/EVO_NIGHT_WATCH.md` (Ring 1):
collect → sanitize → SQLite/FTS5 → aggregate → Ollama local opcional → Markdown.
Sem sandbox apply, Night Watch promotion ou chamadas de nuvem.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
