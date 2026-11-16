"""Entrevista YBY-BRIEF: perguntas, retomada e proposta (sem plano/código)."""

from __future__ import annotations

import re
import secrets
from typing import Callable

from src.brief.schemas import BRIEF_FIELDS, YbyBrief
from src.engine.secret_gate import find_secret, redact_for_cloud

_VAGUE_IDEA = re.compile(
    r"^(oi|olá|ola|ajuda|help|app|site|sistema|ideia)\b",
    re.IGNORECASE,
)


class BriefError(ValueError):
    """Estado inválido do brief."""


def start_brief(idea: str) -> tuple[YbyBrief, list[str]]:
    """Cria draft; ideia vaga já devolve perguntas (não inventa campos)."""

    cleaned = " ".join(idea.strip().split())
    if not cleaned:
        raise BriefError("informe uma ideia em linguagem natural")
    brief = YbyBrief(id=_new_id(), idea=cleaned)
    questions = next_questions(brief)
    if _is_vague_idea(cleaned):
        questions = [
            "A ideia está genérica demais. O que o software deve fazer de concreto?",
            *questions[:2],
        ]
    return brief, questions[:3]


def next_questions(brief: YbyBrief, *, limit: int = 3) -> list[str]:
    """Próximos campos vazios — blocos curtos (máx. `limit`)."""

    out: list[str] = []
    for key, prompt in BRIEF_FIELDS:
        if brief.filled(key):
            continue
        out.append(prompt)
        if len(out) >= limit:
            break
    return out


def missing_fields(brief: YbyBrief) -> list[str]:
    return [key for key, _ in BRIEF_FIELDS if not brief.filled(key)]


def answer_field(brief: YbyBrief, field: str, text: str) -> YbyBrief:
    """Preenche um campo; marca sensível se `find_secret` disparar."""

    keys = {key for key, _ in BRIEF_FIELDS}
    if field not in keys:
        raise BriefError(f"campo desconhecido: {field}")
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        raise BriefError("resposta vazia")
    hit = find_secret(cleaned)
    value = cleaned
    if hit is not None:
        if hit.kind not in brief.sensitive_kinds:
            brief.sensitive_kinds.append(hit.kind)
        value = redact_for_cloud(cleaned)
    setattr(brief, field, value)
    brief.status = "ready" if not missing_fields(brief) else "draft"
    if brief.status == "draft":
        brief.proposal = None
    brief.touch()
    return brief


def try_propose(brief: YbyBrief) -> str:
    """Só gera proposta textual se completo. Não é plano nem autorização."""

    missing = missing_fields(brief)
    if missing:
        raise BriefError(
            "brief incompleto; faltam: " + ", ".join(missing) + " — plano não gerado"
        )
    lines = [
        "Proposta (rascunho local — não é plano nem autorização de execução)",
        f"Ideia: {brief.idea}",
        f"Objetivo: {brief.objective}",
        f"Público: {brief.audience}",
        f"Escopo: {brief.scope}",
        f"Fora de escopo: {brief.out_of_scope}",
        f"Restrições: {brief.constraints}",
        f"Dados: {brief.required_data}",
        f"Aceite: {brief.acceptance}",
        f"Riscos: {brief.risks}",
        "Próximo: lote 15 (plano verificável) após aprovação humana do brief.",
    ]
    if brief.sensitive_kinds:
        lines.append(
            "Atenção: campos com dado sensível foram redigidos "
            f"({', '.join(brief.sensitive_kinds)}); não enviar à nuvem sem revisão."
        )
    proposal = "\n".join(lines)
    brief.proposal = proposal
    brief.status = "proposed"
    brief.touch()
    return proposal


def format_status(brief: YbyBrief) -> str:
    missing = missing_fields(brief)
    lines = [
        f"id: {brief.id}",
        f"status: {brief.status}",
        f"ideia: {brief.idea}",
        f"faltam: {', '.join(missing) if missing else '(nenhum)'}",
    ]
    if brief.sensitive_kinds:
        lines.append(f"sensível: {', '.join(brief.sensitive_kinds)}")
    qs = next_questions(brief)
    if qs:
        lines.append("próximas perguntas:")
        for index, q in enumerate(qs, start=1):
            lines.append(f"  {index}. {q}")
    return "\n".join(lines)


def _is_vague_idea(idea: str) -> bool:
    if len(idea) < 12:
        return True
    return bool(_VAGUE_IDEA.match(idea))


def _new_id() -> str:
    return secrets.token_hex(4)


# Tipagem auxiliar para stores injetáveis em testes.
SaveFn = Callable[[YbyBrief], None]
