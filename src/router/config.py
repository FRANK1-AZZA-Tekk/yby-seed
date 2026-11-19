"""Configuração central do roteador offline. Sem rede e sem segredos."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from src.router.errors import ConfigurationError, ModelNotFoundError, SafetyViolationError
from src.router.schemas import (
    DEFAULT_LANGUAGE,
    DEFAULT_MAX_STEPS,
    DEFAULT_MAX_TOOL_CALLS,
    DEFAULT_TIMEOUT_SECONDS,
    INTENTS,
    MAX_TIMEOUT_SECONDS,
    RISK_LEVELS,
    Constraints,
    Intent,
    ModelProfile,
    RiskLevel,
    RoutingPolicy,
)

DEFAULT_LOCAL_MODEL = "qwen2.5-coder:3b"
DEFAULT_PROFILE_NAME = "general"


def default_profiles(model: str = DEFAULT_LOCAL_MODEL) -> tuple[ModelProfile, ...]:
    """Quatro perfis estáticos mapeando intenções para o mesmo modelo local."""

    return (
        ModelProfile(
            name="general",
            model=model,
            intents=("general",),
            description="Conversação geral local.",
        ),
        ModelProfile(
            name="coding",
            model=model,
            intents=("coding",),
            description="Código e tarefas de programação locais.",
        ),
        ModelProfile(
            name="knowledge",
            model=model,
            intents=("knowledge",),
            description="Consulta e explicação de conhecimento local.",
        ),
        ModelProfile(
            name="automation",
            model=model,
            intents=("automation",),
            description="Automação com aprovação humana obrigatória.",
        ),
    )


def default_constraints() -> Constraints:
    return Constraints(
        max_steps=DEFAULT_MAX_STEPS,
        max_tool_calls=DEFAULT_MAX_TOOL_CALLS,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        allow_cloud=False,
    )


def default_policy(*, model: str = DEFAULT_LOCAL_MODEL) -> RoutingPolicy:
    return RoutingPolicy(
        language=DEFAULT_LANGUAGE,
        intents=INTENTS,
        risk_levels=RISK_LEVELS,
        default_model=model,
        fallback_model=model,
        constraints=default_constraints(),
        profiles=default_profiles(model),
    )


@dataclass(frozen=True)
class RouterConfig:
    """Configuração central do roteador. Pura: não chama Ollama nem nuvem."""

    language: str
    default_model: str
    fallback_model: str
    max_steps: int
    max_tool_calls: int
    timeout_seconds: float
    allow_cloud: bool
    policy: RoutingPolicy

    @classmethod
    def default(cls) -> RouterConfig:
        """Configuração válida pronta para testes e para a Tarefa 2."""

        policy = default_policy()
        return cls.from_policy(policy)

    @classmethod
    def from_policy(cls, policy: RoutingPolicy) -> RouterConfig:
        constraints = policy.constraints
        if constraints.allow_cloud:
            raise ConfigurationError(
                "allow_cloud deve ser false na configuração do roteador offline."
            )
        return cls(
            language=policy.language,
            default_model=policy.default_model,
            fallback_model=policy.fallback_model,
            max_steps=constraints.max_steps,
            max_tool_calls=constraints.max_tool_calls,
            timeout_seconds=constraints.timeout_seconds,
            allow_cloud=False,
            policy=policy,
        )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> RouterConfig:
        """Lê apenas variáveis `YBY_ROUTER_*`. Sem chaves e sem URLs de nuvem."""

        source: Mapping[str, str] = os.environ if environ is None else environ
        model = _text(source, "YBY_ROUTER_LOCAL_MODEL") or DEFAULT_LOCAL_MODEL
        language = _text(source, "YBY_ROUTER_LANGUAGE") or DEFAULT_LANGUAGE
        fallback = _text(source, "YBY_ROUTER_FALLBACK_MODEL") or model
        max_steps = _positive_int(
            source, "YBY_ROUTER_MAX_STEPS", DEFAULT_MAX_STEPS, upper=DEFAULT_MAX_STEPS
        )
        max_tool_calls = _non_negative_int(
            source,
            "YBY_ROUTER_MAX_TOOL_CALLS",
            DEFAULT_MAX_TOOL_CALLS,
            upper=DEFAULT_MAX_STEPS,
        )
        timeout_seconds = _positive_float(
            source,
            "YBY_ROUTER_TIMEOUT_SECONDS",
            DEFAULT_TIMEOUT_SECONDS,
            upper=MAX_TIMEOUT_SECONDS,
        )
        allow_cloud = _false_only(source, "YBY_ROUTER_ALLOW_CLOUD")

        if max_tool_calls > max_steps:
            raise ConfigurationError(
                "YBY_ROUTER_MAX_TOOL_CALLS deve ser menor ou igual a YBY_ROUTER_MAX_STEPS."
            )
        if allow_cloud:
            raise ConfigurationError(
                "YBY_ROUTER_ALLOW_CLOUD deve ser false (roteador offline)."
            )

        profiles = list(default_profiles(model))
        if fallback != model:
            profiles.append(
                ModelProfile(
                    name="fallback",
                    model=fallback,
                    intents=("general",),
                    description="Modelo local de fallback.",
                )
            )
        try:
            policy = RoutingPolicy(
                language=language,
                intents=INTENTS,
                risk_levels=RISK_LEVELS,
                default_model=model,
                fallback_model=fallback,
                constraints=Constraints(
                    max_steps=max_steps,
                    max_tool_calls=max_tool_calls,
                    timeout_seconds=timeout_seconds,
                    allow_cloud=False,
                ),
                profiles=tuple(profiles),
            )
        except Exception as exc:  # pydantic ValidationError e ValueError
            raise ConfigurationError(f"configuração inválida do roteador: {exc}") from exc

        return cls.from_policy(policy)

    def profile_for_intent(self, intent: Intent) -> ModelProfile:
        for profile in self.policy.profiles:
            if intent in profile.intents:
                return profile
        raise ModelNotFoundError(f"nenhum perfil cobre a intenção {intent!r}.")

    def get_profile(self, name: str) -> ModelProfile:
        for profile in self.policy.profiles:
            if profile.name == name:
                return profile
        raise ModelNotFoundError(f"perfil não encontrado: {name!r}.")

    def constraints(self) -> Constraints:
        return Constraints(
            max_steps=self.max_steps,
            max_tool_calls=self.max_tool_calls,
            timeout_seconds=self.timeout_seconds,
            allow_cloud=False,
        )

    def enforce_safety(
        self,
        *,
        intent: Intent,
        risk: RiskLevel,
        requires_approval: bool,
        allow_cloud: bool = False,
        max_steps: int | None = None,
        max_tool_calls: int | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        """Valida limites e regras de aprovação. Não executa nada."""

        if allow_cloud:
            raise SafetyViolationError(
                "allow_cloud=true viola a política offline do roteador."
            )
        steps = self.max_steps if max_steps is None else max_steps
        tools = self.max_tool_calls if max_tool_calls is None else max_tool_calls
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        if steps < 1 or steps > DEFAULT_MAX_STEPS:
            raise SafetyViolationError(
                f"max_steps fora do intervalo permitido (1..{DEFAULT_MAX_STEPS})."
            )
        if tools < 0 or tools > DEFAULT_MAX_STEPS or tools > steps:
            raise SafetyViolationError(
                "max_tool_calls fora do intervalo permitido ou maior que max_steps."
            )
        if timeout <= 0 or timeout > MAX_TIMEOUT_SECONDS:
            raise SafetyViolationError(
                f"timeout_seconds fora do intervalo permitido (0 < t <= {MAX_TIMEOUT_SECONDS})."
            )
        if risk == "high" and not requires_approval:
            raise SafetyViolationError("risco high exige requires_approval=true.")
        if intent == "automation" and not requires_approval:
            raise SafetyViolationError(
                "intenção automation exige requires_approval=true."
            )


def _text(source: Mapping[str, str], name: str) -> str:
    return source.get(name, "").strip()


def _positive_int(
    source: Mapping[str, str], name: str, default: int, *, upper: int
) -> int:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} deve ser um inteiro, recebi {raw!r}.") from exc
    if value < 1 or value > upper:
        raise ConfigurationError(f"{name} deve estar entre 1 e {upper}.")
    return value


def _non_negative_int(
    source: Mapping[str, str], name: str, default: int, *, upper: int
) -> int:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} deve ser um inteiro, recebi {raw!r}.") from exc
    if value < 0 or value > upper:
        raise ConfigurationError(f"{name} deve estar entre 0 e {upper}.")
    return value


def _positive_float(
    source: Mapping[str, str], name: str, default: float, *, upper: float
) -> float:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} deve ser um número, recebi {raw!r}.") from exc
    if value <= 0 or value > upper:
        raise ConfigurationError(f"{name} deve ser maior que 0 e no máximo {upper}.")
    return value


def _false_only(source: Mapping[str, str], name: str) -> bool:
    raw = source.get(name, "").strip()
    if not raw:
        return False
    folded = raw.casefold()
    if folded in {"0", "false", "no", "não", "nao", "off"}:
        return False
    if folded in {"1", "true", "yes", "sim", "on"}:
        return True
    raise ConfigurationError(
        f"{name} deve ser false (ou true apenas para rejeição explícita), recebi {raw!r}."
    )
