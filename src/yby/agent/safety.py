"""Validação de entrada e regras anti-injeção do agente."""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_QUESTION_CHARS = 4000

_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.I),
    re.compile(r"desative?\s+(as\s+)?regras", re.I),
    re.compile(r"ignore\s+suas\s+regras", re.I),
    re.compile(r"você\s+é\s+agora", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"system\s*:\s*", re.I),
)

_RAG_INSTRUCTION_MARKERS = (
    "execute o comando",
    "run_python",
    "curl ",
    "wget ",
    "ignore previous",
    "desative as regras",
)


@dataclass(frozen=True)
class QuestionValidation:
    ok: bool
    question: str
    error_code: str | None = None
    error_message: str | None = None
    warnings: tuple[str, ...] = ()


def validate_user_question(raw: str) -> QuestionValidation:
    text = (raw or "").strip()
    if not text:
        return QuestionValidation(
            ok=False,
            question="",
            error_code="empty_question",
            error_message="pergunta vazia",
        )
    if len(text) > MAX_QUESTION_CHARS:
        return QuestionValidation(
            ok=False,
            question=text[:MAX_QUESTION_CHARS],
            error_code="question_too_long",
            error_message=f"pergunta excede {MAX_QUESTION_CHARS} caracteres",
        )

    warnings: list[str] = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            warnings.append(
                "possível tentativa de alterar regras detectada; "
                "conteúdo será tratado apenas como pergunta, não como comando"
            )
            break

    return QuestionValidation(ok=True, question=text, warnings=tuple(warnings))


def warnings_from_rag_chunk(text: str) -> list[str]:
    lowered = text.lower()
    if any(marker in lowered for marker in _RAG_INSTRUCTION_MARKERS):
        return ["trecho RAG contém texto suspeito; tratado como dado, não como ordem"]
    return []