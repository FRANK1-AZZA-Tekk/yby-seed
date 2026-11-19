"""Testes da política de perfis e segurança do roteador."""

from __future__ import annotations

import pytest

from src.router.errors import ModelNotFoundError, SafetyViolationError
from src.router.policy import (
    ALLOWED_TOOLS,
    INTENT_PROFILES,
    MODEL_AUTOMATION,
    MODEL_CODING,
    MODEL_FALLBACK,
    MODEL_GENERAL,
    MODEL_KNOWLEDGE,
    default_routing_policy,
    elevate_risk,
    fallback_for_intent,
    profile_for_intent,
    raise_if_tools_outside_registry,
    validate_route_decision,
)
from src.router.schemas import Constraints, RouteDecision


def test_profiles_and_fallbacks_for_all_intents() -> None:
    assert profile_for_intent("general").selected_model == MODEL_GENERAL
    assert profile_for_intent("coding").selected_model == MODEL_CODING
    assert profile_for_intent("knowledge").selected_model == MODEL_KNOWLEDGE
    assert profile_for_intent("automation").selected_model == MODEL_AUTOMATION
    for intent in INTENT_PROFILES:
        assert fallback_for_intent(intent) == MODEL_FALLBACK


def test_knowledge_uses_rag_automation_uses_tools() -> None:
    assert profile_for_intent("knowledge").uses_rag is True
    assert profile_for_intent("knowledge").requires_tools is False
    assert profile_for_intent("automation").requires_tools is True
    assert profile_for_intent("automation").min_risk == "medium"


def test_default_routing_policy_is_offline() -> None:
    policy = default_routing_policy()
    assert policy.language == "pt-BR"
    assert policy.constraints.allow_cloud is False
    assert policy.fallback_model == MODEL_FALLBACK
    names = {p.name for p in policy.profiles}
    assert {"general", "coding", "knowledge", "automation", "fallback"} <= names


def test_allowed_tools_match_registry_subset() -> None:
    assert ALLOWED_TOOLS == frozenset({"echo_json", "vault_search"})
    raise_if_tools_outside_registry(["echo_json", "vault_search"])
    with pytest.raises(SafetyViolationError, match="fora do registry"):
        raise_if_tools_outside_registry(["shell_run"])


def test_elevate_risk_and_validate_automation() -> None:
    assert elevate_risk("low", "medium") == "medium"
    assert elevate_risk("high", "medium") == "high"
    decision = RouteDecision(
        intent="automation",
        risk="medium",
        requires_tools=True,
        requires_approval=True,
        selected_model=MODEL_AUTOMATION,
        selected_profile="automation",
        fallback_model=MODEL_FALLBACK,
        confidence=0.9,
        reason="teste automation",
        constraints=Constraints(allow_cloud=False),
    )
    assert validate_route_decision(decision).intent == "automation"


def test_validate_rejects_cloud_and_low_risk_automation() -> None:
    with pytest.raises(SafetyViolationError, match="risk >= medium"):
        validate_route_decision(
            RouteDecision.model_construct(
                intent="automation",
                risk="low",
                requires_tools=True,
                requires_approval=True,
                selected_model=MODEL_AUTOMATION,
                selected_profile="automation",
                fallback_model=MODEL_FALLBACK,
                confidence=0.9,
                reason="bypass",
                constraints=Constraints(allow_cloud=False),
            )
        )
    with pytest.raises(SafetyViolationError, match="allow_cloud"):
        validate_route_decision(
            RouteDecision.model_construct(
                intent="general",
                risk="low",
                requires_tools=False,
                requires_approval=False,
                selected_model=MODEL_GENERAL,
                selected_profile="general",
                fallback_model=MODEL_FALLBACK,
                confidence=0.5,
                reason="cloud",
                constraints=Constraints.model_construct(allow_cloud=True),
            )
        )


def test_unknown_intent_profile_error() -> None:
    with pytest.raises(ModelNotFoundError):
        profile_for_intent("hacking")  # type: ignore[arg-type]
