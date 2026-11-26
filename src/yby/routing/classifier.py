"""Classificador cognitivo em dois estágios (regras <5 ms + triagem opcional)."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from src.engine.routing import DEFAULT_HEAVY_PHRASES, decide_route
from src.yby.routing.schemas import (
    PrivacyGateDecision,
    RouteRequest,
    RouteTier,
    TriageSchema,
)

TriageRunner = Callable[[RouteRequest], Awaitable[TriageSchema | None]]

_CODE_RAG_PATTERN = re.compile(
    r"\b(?:yby[- ]?f[oó]rum|yby[- ]?spec|pwa|pgvector|rag|hermes|fastapi|sql|postgres|"
    r"python|typescript|refactor|refator|diff|pytest|debug|stacktrace|c[oó]digo|implementar)\b",
    re.IGNORECASE,
)

_WEB_FRONTIER_PATTERN = re.compile(
    r"\b(?:pesquis(?:a|ar)\s+web|web\s+search|perplexity|latest\s+release|"
    r"arquitetura\s+complexa|comparar\s+benchmarks|estado\s+da\s+arte)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ClassificationResult:
    """Resultado do classificador com nível escolhido e justificativas."""

    tier: RouteTier
    reasons: tuple[str, ...]
    triage: TriageSchema | None = None


def classify_deterministic(
    request: RouteRequest,
    privacy: PrivacyGateDecision,
) -> ClassificationResult:
    """Estágio 1: heurística pura em memória (<5 ms, sem I/O)."""

    reasons: list[str] = []

    if request.preferred_tier is not None:
        if request.preferred_tier == "yby-cloud-frontier" and not privacy.allow_cloud:
            reasons.append(
                "preferred_tier=yby-cloud-frontier bloqueado pelo PrivacyGate -> yby-code"
            )
            return ClassificationResult(tier="yby-code", reasons=tuple(reasons))
        reasons.append(f"preferred_tier={request.preferred_tier}")
        return ClassificationResult(tier=request.preferred_tier, reasons=tuple(reasons))

    if request.origin in {"raw_audio", "mqtt_telemetry"}:
        reasons.append(f"origin={request.origin} -> triagem rápida local")
        return ClassificationResult(tier="yby-fast", reasons=tuple(reasons))

    legacy_decision = decide_route(
        request.prompt,
        explicit_heavy=request.explicit_heavy,
        heavy_min_chars=1200,
        heavy_min_lines=25,
        heavy_min_questions=3,
        heavy_phrases=DEFAULT_HEAVY_PHRASES,
    )

    wants_cloud = (
        request.requires_web
        or request.origin == "web_research"
        or bool(_WEB_FRONTIER_PATTERN.search(request.prompt))
        or legacy_decision.target == "cloud"
    )
    if wants_cloud:
        if request.requires_web or request.origin == "web_research":
            reasons.append("demanda pesquisa web")
        if _WEB_FRONTIER_PATTERN.search(request.prompt):
            reasons.append("sinal de arquitetura complexa/pesquisa")
        if legacy_decision.target == "cloud":
            reasons.extend(legacy_decision.reasons)

        if privacy.allow_cloud:
            return ClassificationResult(tier="yby-cloud-frontier", reasons=tuple(reasons))

        reasons.append("PrivacyGate bloqueou nuvem -> degradado para yby-code")
        return ClassificationResult(tier="yby-code", reasons=tuple(reasons))

    if request.origin in {"code_workspace", "pgvector", "personal_memory"}:
        reasons.append(f"origin={request.origin} -> síntese 7B híbrida")
        return ClassificationResult(tier="yby-code", reasons=tuple(reasons))

    if _CODE_RAG_PATTERN.search(request.prompt) or len(request.prompt.strip()) >= 280:
        reasons.append("sinal de código/RAG/PWA -> yby-code")
        return ClassificationResult(tier="yby-code", reasons=tuple(reasons))

    reasons.append("comando curto/triagem padrão -> yby-fast")
    return ClassificationResult(tier="yby-fast", reasons=tuple(reasons))


async def classify_request(
    request: RouteRequest,
    privacy: PrivacyGateDecision,
    *,
    triage_runner: TriageRunner | None = None,
) -> ClassificationResult:
    """Estágio 1 determinístico + estágio 2 opcional (GBNF/XGrammar em 3B–4B)."""

    base = classify_deterministic(request, privacy)
    if triage_runner is None or request.preferred_tier is not None:
        return base

    triage = await triage_runner(request)
    if triage is None:
        return base

    suggested = triage.suggested_tier
    reasons = list(base.reasons)
    reasons.append(f"triage_3b:{triage.intent}({triage.confidence:.2f})")

    if suggested == "yby-cloud-frontier" and not privacy.allow_cloud:
        reasons.append("triage sugeriu nuvem, mas PrivacyGate restringiu ao local -> yby-code")
        return ClassificationResult(tier="yby-code", reasons=tuple(reasons), triage=triage)

    return ClassificationResult(tier=suggested, reasons=tuple(reasons), triage=triage)
