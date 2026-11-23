"""Classificador determinístico por regras (sem LLM, sem Ollama)."""

from __future__ import annotations

import re
import uuid
from typing import Mapping

from pydantic import ValidationError

from src.router.errors import RoutingError
from src.router.policy import (
    elevate_risk,
    profile_for_intent,
    raise_if_tools_outside_registry,
    validate_route_decision,
)
from src.router.schemas import (
    DEFAULT_LANGUAGE,
    Constraints,
    Intent,
    Request,
    RiskLevel,
    RouteDecision,
    RouterResult,
)

# Ordem de prioridade: automation > coding > knowledge > general.
_AUTOMATION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bautomatiz",
        r"\bagendar\b",
        r"\bcron\b",
        r"\bexecut(e|ar|a)\b",
        r"\brodar\b",
        r"\bcomando\b",
        r"\bscript\b",
        r"\bworkflow\b",
        r"\bpipeline\b",
        r"\btool(?:s)?\b",
        r"\bferramenta(?:s)?\b",
        r"\bshell\b",
        r"\bsubprocess\b",
        r"\byby\s+run\b",
    )
)

_CODING_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bc[oó]digo\b",
        r"\bcode\b",
        r"\bpython\b",
        r"\btypescript\b",
        r"\bjavascript\b",
        r"\bfun[cç][aã]o\b",
        r"\bclass\b",
        r"\bclasse\b",
        r"\bbug\b",
        r"\brefator",
        r"\bimplement",
        r"\bcompil",
        r"\bpytest\b",
        r"\bunit\s*test\b",
        r"\bapi\b",
        r"\bsrc/",
        r"\bdef\s+\w+",
        r"\bimport\s+\w+",
    )
)

_KNOWLEDGE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bo\s+que\s+[eé]\b",
        r"\bwhat\s+is\b",
        r"\bexpli(?:que|car|ca)\b",
        r"\bpesqui(?:se|sar|sa)\b",
        r"\bdocumenta[cç][aã]o\b",
        r"\brag\b",
        r"\bvault\b",
        r"\bconhecimento\b",
        r"\bhist[oó]ria\b",
        r"\bdefin[ií][cç]",
        r"\bresuma\b",
        r"\bcomo\s+funciona\b",
    )
)

_HIGH_RISK_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\brm\s+-rf\b",
        r"\bformatar\s+disco\b",
        r"\bapagar\s+tudo\b",
        r"\bdelete\s+all\b",
        r"\bdrop\s+table\b",
        r"\bsenha\b",
        r"\bpassword\b",
        r"\bapi[_-]?key\b",
        r"\bcredential",
        r"\bsudo\s+rm\b",
        r"\bexfiltr",
    )
)

_MEDIUM_RISK_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\binstalar\b",
        r"\binstall\b",
        r"\bescrever\s+arquivo\b",
        r"\bwrite\s+file\b",
        r"\bmodificar\s+sistema\b",
        r"\bchmod\b",
        r"\bchown\b",
        r"\bsudo\b",
        r"\breboot\b",
        r"\bsystemctl\b",
    )
)

_KNOWN_TOOL_HINTS = frozenset(
    {
        "echo_json",
        "vault_search",
        "shell_run",
        "shell",
        "file_write",
        "file_read",
        "browser",
        "http_request",
    }
)
_TOOL_NAME_PATTERN = re.compile(
    r"\b("
    + "|".join(
        re.escape(name) for name in sorted(_KNOWN_TOOL_HINTS, key=len, reverse=True)
    )
    + r")\b",
    re.IGNORECASE,
)


def classify(request: Request | Mapping[str, object] | str) -> RouteDecision:
    """Classifica um pedido e devolve `RouteDecision` estruturada."""

    parsed = _coerce_request(request)
    text = parsed.text.strip()
    folded = text.casefold()

    intent, intent_hits = _detect_intent(folded)
    risk, risk_hits = _detect_risk(folded)
    mentioned_tools = _extract_tool_mentions(folded)
    raise_if_tools_outside_registry(mentioned_tools)

    spec = profile_for_intent(intent)
    risk = elevate_risk(risk, spec.min_risk)

    requires_tools = bool(spec.requires_tools or mentioned_tools)
    if intent == "knowledge" and spec.uses_rag:
        # RAG é capacidade do perfil; não é tool do registry.
        requires_tools = False if not mentioned_tools else True

    requires_approval = bool(
        intent == "automation" or risk == "high" or (risk == "medium" and requires_tools)
    )
    if intent == "automation":
        requires_approval = True
        requires_tools = True

    language = _detect_language(parsed.language, text)
    confidence = _confidence(intent_hits, risk_hits, intent)
    reason = _build_reason(
        intent=intent,
        risk=risk,
        language=language,
        intent_hits=intent_hits,
        risk_hits=risk_hits,
        uses_rag=spec.uses_rag,
        requires_tools=requires_tools,
        mentioned_tools=mentioned_tools,
    )

    try:
        decision = RouteDecision(
            intent=intent,
            risk=risk,
            requires_tools=requires_tools,
            requires_approval=requires_approval,
            selected_model=spec.selected_model,
            selected_profile=spec.profile,
            fallback_model=spec.fallback_model,
            confidence=confidence,
            reason=reason,
            constraints=Constraints(allow_cloud=False),
        )
    except ValidationError as exc:
        raise RoutingError(f"decisão inválida: {exc}") from exc

    return validate_route_decision(decision)


def classify_result(request: Request | Mapping[str, object] | str) -> RouterResult:
    """Atalho: pedido + decisão."""

    parsed = _coerce_request(request)
    return RouterResult(request=parsed, decision=classify(parsed))


def _coerce_request(request: Request | Mapping[str, object] | str) -> Request:
    if isinstance(request, Request):
        return request
    if isinstance(request, str):
        text = request.strip()
        if not text:
            raise RoutingError("entrada inválida: texto vazio.")
        return Request(
            request_id=f"req-{uuid.uuid4().hex[:12]}",
            input_type="text",
            language=DEFAULT_LANGUAGE,
            text=text,
        )
    try:
        return Request.model_validate(request)
    except ValidationError as exc:
        raise RoutingError(f"entrada inválida: {exc}") from exc


def _detect_intent(folded: str) -> tuple[Intent, list[str]]:
    hits: list[str] = []
    for pattern in _AUTOMATION_PATTERNS:
        if pattern.search(folded):
            hits.append(pattern.pattern)
    if hits:
        return "automation", hits[:3]

    for pattern in _CODING_PATTERNS:
        if pattern.search(folded):
            hits.append(pattern.pattern)
    if hits:
        return "coding", hits[:3]

    for pattern in _KNOWLEDGE_PATTERNS:
        if pattern.search(folded):
            hits.append(pattern.pattern)
    if hits:
        return "knowledge", hits[:3]

    return "general", []


def _detect_risk(folded: str) -> tuple[RiskLevel, list[str]]:
    high_hits = [p.pattern for p in _HIGH_RISK_PATTERNS if p.search(folded)]
    if high_hits:
        return "high", high_hits[:3]
    medium_hits = [p.pattern for p in _MEDIUM_RISK_PATTERNS if p.search(folded)]
    if medium_hits:
        return "medium", medium_hits[:3]
    return "low", []


def _extract_tool_mentions(folded: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _TOOL_NAME_PATTERN.finditer(folded):
        token = match.group(1).casefold()
        if token not in seen:
            seen.add(token)
            found.append(token)
    return found


def _detect_language(declared: str, text: str) -> str:
    cleaned = declared.strip() or DEFAULT_LANGUAGE
    if cleaned != DEFAULT_LANGUAGE:
        return cleaned
    # Heurística leve: presença de termos tipicamente em inglês sem pt.
    sample = text.casefold()
    pt_markers = ("ção", "ões", "não", "você", "para", "que", "uma", "com")
    en_markers = (" the ", " what ", " please ", " could ", " should ")
    if any(m in sample for m in en_markers) and not any(m in sample for m in pt_markers):
        return "en"
    return DEFAULT_LANGUAGE


def _confidence(intent_hits: list[str], risk_hits: list[str], intent: Intent) -> float:
    if intent == "general" and not intent_hits:
        return 0.55
    base = 0.7 + 0.08 * min(len(intent_hits), 3)
    if risk_hits:
        base += 0.05
    return round(min(base, 0.98), 2)


def _build_reason(
    *,
    intent: Intent,
    risk: RiskLevel,
    language: str,
    intent_hits: list[str],
    risk_hits: list[str],
    uses_rag: bool,
    requires_tools: bool,
    mentioned_tools: list[str],
) -> str:
    parts = [
        f"intent={intent}",
        f"risk={risk}",
        f"language={language}",
        "allow_cloud=false",
    ]
    if intent_hits:
        parts.append("regras_intent=" + "|".join(intent_hits))
    else:
        parts.append("regras_intent=default_general")
    if risk_hits:
        parts.append("regras_risk=" + "|".join(risk_hits))
    if uses_rag:
        parts.append("capabilities=rag")
    if requires_tools:
        tools = ",".join(mentioned_tools) if mentioned_tools else "registry"
        parts.append(f"capabilities=tools:{tools}")
    return "; ".join(parts)
