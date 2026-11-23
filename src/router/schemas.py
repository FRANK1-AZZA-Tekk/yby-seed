"""Modelos Pydantic da fundação do roteador offline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Intent = Literal["general", "coding", "knowledge", "automation"]
RiskLevel = Literal["low", "medium", "high"]
InputType = Literal["text"]

INTENTS: tuple[Intent, ...] = ("general", "coding", "knowledge", "automation")
RISK_LEVELS: tuple[RiskLevel, ...] = ("low", "medium", "high")
DEFAULT_LANGUAGE = "pt-BR"
DEFAULT_MAX_STEPS = 8
DEFAULT_MAX_TOOL_CALLS = 4
DEFAULT_TIMEOUT_SECONDS = 120.0
MAX_TIMEOUT_SECONDS = 120.0


class Constraints(BaseModel):
    """Limites de segurança aplicados a uma decisão de rota."""

    model_config = ConfigDict(extra="forbid")

    max_steps: int = Field(default=DEFAULT_MAX_STEPS, ge=1, le=DEFAULT_MAX_STEPS)
    max_tool_calls: int = Field(default=DEFAULT_MAX_TOOL_CALLS, ge=0, le=DEFAULT_MAX_STEPS)
    timeout_seconds: float = Field(
        default=DEFAULT_TIMEOUT_SECONDS, gt=0, le=MAX_TIMEOUT_SECONDS
    )
    allow_cloud: bool = False

    @field_validator("allow_cloud")
    @classmethod
    def _cloud_disabled(cls, value: bool) -> bool:
        if value is True:
            raise ValueError(
                "allow_cloud deve ser false nesta fundação (roteador offline local-first)."
            )
        return False

    @model_validator(mode="after")
    def _tool_calls_within_steps(self) -> Constraints:
        if self.max_tool_calls > self.max_steps:
            raise ValueError("max_tool_calls deve ser menor ou igual a max_steps.")
        return self


class Request(BaseModel):
    """Entrada inicial do roteador — somente texto nesta tarefa."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128)
    input_type: InputType = "text"
    language: str = DEFAULT_LANGUAGE
    text: str = Field(min_length=1, max_length=50_000)

    @field_validator("language")
    @classmethod
    def _non_empty_language(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("language não pode ser vazio.")
        return cleaned


class RouteDecision(BaseModel):
    """Decisão de rota pronta para o classificador da Tarefa 2."""

    model_config = ConfigDict(extra="forbid")

    intent: Intent
    risk: RiskLevel
    requires_tools: bool = False
    requires_approval: bool = False
    selected_model: str = Field(min_length=1, max_length=128)
    selected_profile: str = Field(min_length=1, max_length=64)
    fallback_model: str = Field(min_length=1, max_length=128)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=1000)
    constraints: Constraints = Field(default_factory=Constraints)

    @model_validator(mode="after")
    def _approval_for_sensitive(self) -> RouteDecision:
        if self.risk == "high" and not self.requires_approval:
            raise ValueError("risco high exige requires_approval=true.")
        if self.intent == "automation" and not self.requires_approval:
            raise ValueError("intenção automation exige requires_approval=true.")
        return self


class ModelProfile(BaseModel):
    """Perfil estático de modelo local (mapa, não classificador)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128)
    intents: tuple[Intent, ...] = Field(min_length=1)
    local_only: bool = True
    description: str = Field(default="", max_length=500)

    @field_validator("local_only")
    @classmethod
    def _must_be_local(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("local_only deve ser true no roteador offline.")
        return True

    @field_validator("intents")
    @classmethod
    def _unique_intents(cls, value: tuple[Intent, ...]) -> tuple[Intent, ...]:
        if len(set(value)) != len(value):
            raise ValueError("intents não pode repetir valores.")
        return value


class RoutingPolicy(BaseModel):
    """Política de roteamento offline com limites e perfis."""

    model_config = ConfigDict(extra="forbid")

    language: str = DEFAULT_LANGUAGE
    intents: tuple[Intent, ...] = INTENTS
    risk_levels: tuple[RiskLevel, ...] = RISK_LEVELS
    default_model: str = Field(min_length=1, max_length=128)
    fallback_model: str = Field(min_length=1, max_length=128)
    constraints: Constraints = Field(default_factory=Constraints)
    profiles: tuple[ModelProfile, ...] = Field(min_length=1)

    @field_validator("language")
    @classmethod
    def _policy_language(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("language não pode ser vazio.")
        return cleaned

    @model_validator(mode="after")
    def _profiles_cover_defaults(self) -> RoutingPolicy:
        names = {profile.name for profile in self.profiles}
        models = {profile.model for profile in self.profiles}
        if len(names) != len(self.profiles):
            raise ValueError("profiles deve ter nomes únicos.")
        if self.default_model not in models:
            raise ValueError("default_model deve existir em algum profile.model.")
        if self.fallback_model not in models:
            raise ValueError("fallback_model deve existir em algum profile.model.")
        if self.constraints.allow_cloud:
            raise ValueError("allow_cloud deve ser false na política offline.")
        return self


class RouterResult(BaseModel):
    """Resultado completo: pedido original + decisão."""

    model_config = ConfigDict(extra="forbid")

    request: Request
    decision: RouteDecision
