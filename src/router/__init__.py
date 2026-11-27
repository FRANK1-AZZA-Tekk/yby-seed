"""Roteador de IAs offline do YBY — fundação + classificador por regras."""

from src.router.classifier import classify, classify_result
from src.router.config import (
    DEFAULT_LOCAL_MODEL,
    DEFAULT_PROFILE_NAME,
    RouterConfig,
    default_constraints,
    default_policy,
    default_profiles,
)
from src.router.errors import (
    ConfigurationError,
    ModelNotFoundError,
    RouterError,
    RoutingError,
    SafetyViolationError,
)
from src.router.policy import (
    ALLOWED_TOOLS,
    INTENT_PROFILES,
    default_routing_policy,
    fallback_for_intent,
    profile_for_intent,
    validate_route_decision,
)
from src.router.schemas import (
    DEFAULT_LANGUAGE,
    INTENTS,
    RISK_LEVELS,
    Constraints,
    Intent,
    ModelProfile,
    Request,
    RiskLevel,
    RouteDecision,
    RouterResult,
    RoutingPolicy,
)

__all__ = [
    "ALLOWED_TOOLS",
    "ConfigurationError",
    "Constraints",
    "DEFAULT_LANGUAGE",
    "DEFAULT_LOCAL_MODEL",
    "DEFAULT_PROFILE_NAME",
    "INTENT_PROFILES",
    "INTENTS",
    "Intent",
    "ModelNotFoundError",
    "ModelProfile",
    "RISK_LEVELS",
    "Request",
    "RiskLevel",
    "RouteDecision",
    "RouterConfig",
    "RouterError",
    "RouterResult",
    "RoutingError",
    "RoutingPolicy",
    "SafetyViolationError",
    "classify",
    "classify_result",
    "default_constraints",
    "default_policy",
    "default_profiles",
    "default_routing_policy",
    "fallback_for_intent",
    "profile_for_intent",
    "validate_route_decision",
]
