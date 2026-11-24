"""Roteamento local ou nuvem.

Um pedido vai para a nuvem quando qualquer sinal abaixo aparece. Os limites
numéricos vêm de `EngineConfig` (variáveis `YBY_HEAVY_*`).

Sinais, em OU:

1. Pedido explícito: flag `--heavy`, ou uma frase da lista (padrão:
   "pensa mais", "pense mais", "pensar mais", "pensa melhor", "pense melhor",
   "raciocina mais", "raciocine mais", "modo pesado", "think harder",
   "think more", "reason harder"). `YBY_HEAVY_PHRASES` substitui a lista
   quando está definida (frases separadas por vírgula).
2. Tamanho: caracteres do pedido >= `YBY_HEAVY_MIN_CHARS` (padrão 1200),
   ou linhas >= `YBY_HEAVY_MIN_LINES` (padrão 25).
3. Complexidade: quantidade de `?` >= `YBY_HEAVY_MIN_QUESTIONS` (padrão 3).

Sem esses sinais, o destino é o Ollama local. A escolha daqui não consulta
a rede. Falha do Ollama no caminho local não dispara nuvem silenciosa (D12);
nuvem só entra quando o roteamento já pediu (sinais acima / `--heavy`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DEFAULT_HEAVY_PHRASES: tuple[str, ...] = (
    "pensa mais",
    "pense mais",
    "pensar mais",
    "pensa melhor",
    "pense melhor",
    "raciocina mais",
    "raciocine mais",
    "modo pesado",
    "think harder",
    "think more",
    "reason harder",
)

RouteTarget = Literal["local", "cloud"]


@dataclass(frozen=True)
class RouteDecision:
    """Destino escolhido e os motivos que o teste e o CLI podem mostrar."""

    target: RouteTarget
    reasons: tuple[str, ...]
    codes: tuple[str, ...] = ()


def decide_route(
    prompt: str,
    *,
    explicit_heavy: bool,
    heavy_min_chars: int,
    heavy_min_lines: int,
    heavy_min_questions: int,
    heavy_phrases: tuple[str, ...],
) -> RouteDecision:
    """Classifica o pedido. Não chama modelo nenhum."""

    reasons: list[str] = []
    codes: list[str] = []
    folded = prompt.casefold()

    if explicit_heavy:
        reasons.append("flag --heavy")
        codes.append("explicit_heavy")

    for phrase in heavy_phrases:
        needle = phrase.casefold()
        if needle and needle in folded:
            reasons.append(f"frase explícita: {needle}")
            codes.append("heavy_phrase")
            break

    characters = len(prompt.strip())
    if characters >= heavy_min_chars:
        reasons.append(f"tamanho: {characters} caracteres (limite {heavy_min_chars})")
        codes.append("large_prompt")

    lines = _line_count(prompt)
    if lines >= heavy_min_lines:
        reasons.append(f"tamanho: {lines} linhas (limite {heavy_min_lines})")
        codes.append("many_lines")

    questions = prompt.count("?")
    if questions >= heavy_min_questions:
        reasons.append(f"complexidade: {questions} perguntas (limite {heavy_min_questions})")
        codes.append("many_questions")

    if reasons:
        return RouteDecision("cloud", tuple(reasons), tuple(codes))
    return RouteDecision("local", ("pedido dentro do limite local",), ("local_default",))


def route_display_reasons(decision: RouteDecision) -> tuple[str, ...]:
    """Motivos seguros para o CLI `route` (sem ecoar frases de YBY_HEAVY_PHRASES).

    A decisão interna (`decide_route`) mantém `frase explícita: <needle>` para o `ask`;
    aqui só trocamos o rótulo quando o gatilho veio da lista configurável.
    """

    displayed: list[str] = []
    for code, reason in zip(decision.codes, decision.reasons, strict=True):
        if code == "heavy_phrase":
            displayed.append("frase explícita (lista YBY_HEAVY_PHRASES)")
        else:
            displayed.append(reason)
    return tuple(displayed)


def _line_count(prompt: str) -> int:
    if not prompt.strip():
        return 0
    return prompt.count("\n") + 1
