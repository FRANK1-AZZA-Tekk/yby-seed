"""Schemas Pydantic v2 do Módulo A (roteamento em cascata + Privacy Gate)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Sensitivity = Literal["private", "public"]

DataOrigin = Literal[
    "user_prompt",
    "pgvector",
    "personal_memory",
    "mqtt_telemetry",
    "raw_audio",
    "pix_commercial",
    "web_research",
    "code_workspace",
]

RouteTier = Literal[
    "yby-fast",
    "yby-code",
    "yby-cloud-frontier",
    "yby-mobile-fallback",
]

TriageIntent = Literal[
    "voice_command",
    "mqtt_action",
    "code_synthesis",
    "rag_synthesis",
    "web_research",
    "architecture_complex",
    "general_chat",
]

LOCAL_TIERS: tuple[RouteTier, ...] = (
    "yby-fast",
    "yby-code",
    "yby-mobile-fallback",
)

ALL_TIERS: tuple[RouteTier, ...] = (
    "yby-fast",
    "yby-code",
    "yby-cloud-frontier",
    "yby-mobile-fallback",
)


class TriageSchema(BaseModel):
    """Saída estruturada (compatível com GBNF / XGrammar) para triagem em 3B–4B."""

    model_config = ConfigDict(extra="forbid")

    intent: TriageIntent
    suggested_tier: RouteTier
    requires_web: bool = False
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    reason: str = Field(default="", max_length=240)


class RouteRequest(BaseModel):
    """Entrada do roteador cognitivo. Default fail-closed: `sensitivity="private"`."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1)
    sensitivity: Sensitivity = "private"
    origin: DataOrigin = "user_prompt"
    source_node: str = Field(default="desktop-yby", min_length=1, max_length=64)
    preferred_tier: RouteTier | None = None
    requires_web: bool = False
    explicit_heavy: bool = False
    use_cache: bool = True
    system_prompt: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PrivacyGateDecision(BaseModel):
    """Veredito imutável do Privacy Gate antes de qualquer egresso."""

    model_config = ConfigDict(extra="forbid")

    allow_cloud: bool
    effective_sensitivity: Sensitivity
    blocked_reasons: tuple[str, ...] = ()
    allowed_tiers: tuple[RouteTier, ...]
    redaction_count: int = 0
    redacted_types: dict[str, int] = Field(default_factory=dict)
    sanitized_prompt: str


class RouteMetadata(BaseModel):
    """Telemetria estruturada da decisão de roteamento e failover."""

    model_config = ConfigDict(extra="forbid")

    selected_tier: RouteTier
    attempted_tiers: list[RouteTier] = Field(default_factory=list)
    fallback_used: bool = False
    cache_hit: bool = False
    privacy_blocked_cloud: bool = False
    privacy_reasons: list[str] = Field(default_factory=list)
    classifier_reasons: list[str] = Field(default_factory=list)
    redaction_count: int = 0
    latency_ms: float = 0.0


class RouteResponse(BaseModel):
    """Resposta normalizada do CognitiveRouter."""

    model_config = ConfigDict(extra="forbid")

    text: str
    tier: RouteTier
    model: str
    metadata: RouteMetadata
