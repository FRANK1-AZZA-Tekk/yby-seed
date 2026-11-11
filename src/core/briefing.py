"""Modelo de Briefing revisável (Fase 1 / issue #19).

Sem execução de código: só estrutura, validação e exportação local.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Briefing(BaseModel):
    """Briefing estruturado exportável (MD + JSON)."""

    title: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    requirements: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    source_request: str = ""
    mode: str = "basic"
    approved: bool = False
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    @field_validator(
        "requirements",
        "assumptions",
        "open_questions",
        "tasks",
        mode="before",
    )
    @classmethod
    def _coerce_str_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError("esperado lista de strings")

    @field_validator("title", "summary", mode="before")
    @classmethod
    def _strip_required(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("campo obrigatório vazio")
        return text


BRIEFING_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "requirements": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "tasks": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "title",
        "summary",
        "requirements",
        "assumptions",
        "open_questions",
        "tasks",
    ],
}


def slugify(text: str) -> str:
    """Gera slug ASCII simples para nome de arquivo."""
    normalized = text.lower().strip()
    normalized = re.sub(r"[^\w\s-]", "", normalized, flags=re.UNICODE)
    normalized = re.sub(r"[\s_-]+", "-", normalized).strip("-")
    return normalized[:60] or "briefing"


def briefing_to_markdown(briefing: Briefing) -> str:
    """Renderiza o briefing em Markdown legível."""
    lines = [
        f"# {briefing.title}",
        "",
        f"> Gerado em {briefing.created_at} | modo: {briefing.mode}"
        f" | aprovado: {'sim' if briefing.approved else 'não'}",
        "",
    ]
    if briefing.source_request:
        lines.extend(["## Pedido original", "", briefing.source_request, ""])

    lines.extend(["## Resumo", "", briefing.summary, ""])

    def _section(title: str, items: list[str]) -> None:
        lines.append(f"## {title}")
        lines.append("")
        if not items:
            lines.append("- (nenhum)")
        else:
            lines.extend(f"- {item}" for item in items)
        lines.append("")

    _section("Requisitos", briefing.requirements)
    _section("Premissas", briefing.assumptions)
    _section("Perguntas em aberto", briefing.open_questions)
    _section("Tarefas", briefing.tasks)
    lines.append("---")
    lines.append("")
    lines.append("Nenhuma execução automática de código.")
    lines.append("")
    return "\n".join(lines)


def default_briefings_dir(project_root: Path | None = None) -> Path:
    root = project_root or Path.cwd()
    return root / ".yby" / "briefings"


def export_briefing(
    briefing: Briefing,
    output_dir: Path | None = None,
    *,
    project_root: Path | None = None,
) -> tuple[Path, Path]:
    """Exporta Markdown + JSON sob `.yby/briefings/`. Retorna (md_path, json_path)."""
    target = output_dir or default_briefings_dir(project_root)
    target.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    base = f"{stamp}-{slugify(briefing.title)}"
    md_path = target / f"{base}.md"
    json_path = target / f"{base}.json"

    md_path.write_text(briefing_to_markdown(briefing), encoding="utf-8")
    json_path.write_text(
        json.dumps(briefing.model_dump(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return md_path, json_path
