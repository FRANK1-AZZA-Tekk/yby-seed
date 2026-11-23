"""Política determinística de perfis, fallbacks e segurança do roteador."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.router.errors import ModelNotFoundError, SafetyViolationError
from src.router.schemas import (
    DEFAULT_LANGUAGE,
    DEFAULT_MAX_STEPS,
    DEFAULT_MAX_TOOL_CALLS,
    DEFAULT_TIMEOUT_SECONDS,
    INTENTS,
    RISK_LEVELS,
    Constraints,
    Intent,
    ModelProfile,
    RiskLevel,
    RouteDecision,
    RoutingPolicy,
)

# Modelos locais desta tarefa (somente nomes; nenhum peso é carregado).
MODEL_GENERAL = "qwen3-8b-instruct"
MODEL_CODING = "qwen2.5-coder-7b-instruct"
MODEL_KNOWLEDGE = "qwen3-8b-instruct"
MODEL_AUTOMATION = "qwen3-8b-instruct"
MODEL_FALLBACK = "qwen3-4b-instruct"

# Tools permitidas (mesmo registry do agent_loop P0). Sem execução aqui.
ALLOWED_TOOLS: frozenset[str] = frozenset({"echo_json", "vault_search"})

_RISK_RANK: dict[RiskLevel, int] = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True)
class IntentProfile:
    """Mapa estático intenção → modelo / capacidades."""

    intent: Intent
    profile: str
    selected_model: str
    fallback_model: str
    uses_rag: bool = False
    requires_tools: bool = False
    min_risk: RiskLevel = "low"
    description: str = ""


INTENT_PROFILES: dict[Intent, IntentProfile] = {
    "general": IntentProfile(
        intent="general",
        profile="general",
        selected_model=MODEL_GENERAL,
        fallback_model=MODEL_FALLBACK,
        description="Conversação geral local.",
    ),
    "coding": IntentProfile(
        intent="coding",
        profile="coding",
        selected_model=MODEL_CODING,
        fallback_model=MODEL_FALLBACK,
        description="Código e programação locais.",
    ),
    "knowledge": IntentProfile(
        intent="knowledge",
        profile="knowledge",
        selected_model=MODEL_KNOWLEDGE,
        fallback_model=MODEL_FALLBACK,
        uses_rag=True,
        description="Conhecimento local com RAG.",
    ),
    "automation": IntentProfile(
        intent="automation",
        profile="automation",
        selected_model=MODEL_AUTOMATION,
        fallback_model=MODEL_FALLBACK,
        requires_tools=True,
        min_risk="medium",
        description="Automação local com tools e aprovação.",
    ),
}


def classifier_model_profiles() -> tuple[ModelProfile, ...]:
    """Perfis Pydantic alinhados ao mapa da Tarefa 2."""

    profiles: list[ModelProfile] = [
        ModelProfile(
            name=spec.profile,
            model=spec.selected_model,
            intents=(spec.intent,),
            local_only=True,
            description=spec.description,
        )
        for spec in INTENT_PROFILES.values()
    ]
    profiles.append(
        ModelProfile(
            name="fallback",
            model=MODEL_FALLBACK,
            intents=("general",),
            local_only=True,
            description="Fallback local compartilhado.",
        )
    )
    return tuple(profiles)


def default_routing_policy() -> RoutingPolicy:
    """Política offline usada pelo classificador por regras."""

    return RoutingPolicy(
        language=DEFAULT_LANGUAGE,
        intents=INTENTS,
        risk_levels=RISK_LEVELS,
        default_model=MODEL_GENERAL,
        fallback_model=MODEL_FALLBACK,
        constraints=Constraints(
            max_steps=DEFAULT_MAX_STEPS,
            max_tool_calls=DEFAULT_MAX_TOOL_CALLS,
            timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
            allow_cloud=False,
        ),
        profiles=classifier_model_profiles(),
    )


def profile_for_intent(intent: Intent) -> IntentProfile:
    try:
        return INTENT_PROFILES[intent]
    except KeyError as exc:
        raise ModelNotFoundError(f"intenção sem perfil: {intent!r}") from exc


def fallback_for_intent(intent: Intent) -> str:
    return profile_for_intent(intent).fallback_model


def raise_if_tools_outside_registry(tool_names: Iterable[str]) -> None:
    """Garante que nenhuma tool fora do registry seja referenciada."""

    unknown = sorted({name for name in tool_names if name not in ALLOWED_TOOLS})
    if unknown:
        raise SafetyViolationError(
            "ferramentas fora do registry: " + ", ".join(unknown)
        )


def elevate_risk(current: RiskLevel, minimum: RiskLevel) -> RiskLevel:
    if _RISK_RANK[current] >= _RISK_RANK[minimum]:
        return current
    return minimum


def validate_route_decision(decision: RouteDecision) -> RouteDecision:
    """Aplica regras de segurança; nunca permite nuvem nem ignora limites."""

    if decision.constraints.allow_cloud:
        raise SafetyViolationError(
            "allow_cloud=true viola a política offline do roteador."
        )

    constraints = decision.constraints
    if constraints.max_steps < 1 or constraints.max_steps > DEFAULT_MAX_STEPS:
        raise SafetyViolationError(
            f"max_steps fora do intervalo permitido (1..{DEFAULT_MAX_STEPS})."
        )
    if (
        constraints.max_tool_calls < 0
        or constraints.max_tool_calls > DEFAULT_MAX_STEPS
        or constraints.max_tool_calls > constraints.max_steps
    ):
        raise SafetyViolationError(
            "max_tool_calls fora do intervalo permitido ou maior que max_steps."
        )
    if constraints.timeout_seconds <= 0 or constraints.timeout_seconds > 120.0:
        raise SafetyViolationError(
            "timeout_seconds fora do intervalo permitido (0 < t <= 120)."
        )

    spec = profile_for_intent(decision.intent)
    if decision.selected_model != spec.selected_model:
        raise SafetyViolationError(
            f"selected_model {decision.selected_model!r} não bate com o perfil "
            f"{spec.profile!r}."
        )
    if decision.fallback_model != spec.fallback_model:
        raise SafetyViolationError(
            f"fallback_model {decision.fallback_model!r} inválido para "
            f"{decision.intent}."
        )
    if decision.selected_profile != spec.profile:
        raise SafetyViolationError(
            f"selected_profile {decision.selected_profile!r} inválido."
        )

    if decision.intent == "automation":
        if _RISK_RANK[decision.risk] < _RISK_RANK["medium"]:
            raise SafetyViolationError(
                "intenção automation exige risk >= medium."
            )
        if not decision.requires_approval:
            raise SafetyViolationError(
                "intenção automation exige requires_approval=true."
            )
        if not decision.requires_tools:
            raise SafetyViolationError(
                "intenção automation exige requires_tools=true."
            )

    if decision.risk == "high" and not decision.requires_approval:
        raise SafetyViolationError("risco high exige requires_approval=true.")

    # requires_tools implica uso exclusivo do registry allowlisted;
    # menções fora do registry são barradas em raise_if_tools_outside_registry.
    if decision.requires_tools and not ALLOWED_TOOLS:
        raise SafetyViolationError("requires_tools sem registry allowlisted.")

    return decision
