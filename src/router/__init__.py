"""Fundação do roteador de IAs offline do YBY (sem classificador nesta tarefa)."""

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
    "ConfigurationError",
    "Constraints",
    "DEFAULT_LANGUAGE",
    "DEFAULT_LOCAL_MODEL",
    "DEFAULT_PROFILE_NAME",
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
    "default_constraints",
    "default_policy",
    "default_profiles",
]
