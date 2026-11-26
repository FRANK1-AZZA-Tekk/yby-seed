"""Módulo A — Roteador Cognitivo Híbrido com Privacy Gate e failover PocketPal."""

from __future__ import annotations

from src.yby.routing.cache import (
    CacheBackend,
    InMemoryCacheBackend,
    NodeHealthTracker,
    RedisCacheBackend,
    build_cache_key,
)
from src.yby.routing.classifier import ClassificationResult, classify_request
from src.yby.routing.privacy_gate import PRIVATE_ORIGINS, PrivacyGate
from src.yby.routing.router import (
    CognitiveRouter,
    LLMBackend,
    OpenAICompatibleBackend,
    RouterConfig,
    RoutingExhaustedError,
    TierExecutionError,
)
from src.yby.routing.schemas import (
    DataOrigin,
    PrivacyGateDecision,
    RouteMetadata,
    RouteRequest,
    RouteResponse,
    RouteTier,
    Sensitivity,
    TriageIntent,
    TriageSchema,
)

__all__ = [
    "PRIVATE_ORIGINS",
    "CacheBackend",
    "ClassificationResult",
    "CognitiveRouter",
    "DataOrigin",
    "InMemoryCacheBackend",
    "LLMBackend",
    "NodeHealthTracker",
    "OpenAICompatibleBackend",
    "PrivacyGate",
    "PrivacyGateDecision",
    "RedisCacheBackend",
    "RouteMetadata",
    "RouteRequest",
    "RouteResponse",
    "RouteTier",
    "RouterConfig",
    "RoutingExhaustedError",
    "Sensitivity",
    "TierExecutionError",
    "TriageIntent",
    "TriageSchema",
    "build_cache_key",
    "classify_request",
]
