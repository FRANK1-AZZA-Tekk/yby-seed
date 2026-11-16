"""Testes dos schemas Pydantic do roteador offline."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.router.config import DEFAULT_LOCAL_MODEL, default_policy
from src.router.schemas import (
    Constraints,
    ModelProfile,
    Request,
    RouteDecision,
    RouterResult,
    RoutingPolicy,
)


def _decision(**overrides: object) -> RouteDecision:
    payload: dict[str, object] = {
        "intent": "general",
        "risk": "low",
        "requires_tools": False,
        "requires_approval": False,
        "selected_model": DEFAULT_LOCAL_MODEL,
        "selected_profile": "general",
        "fallback_model": DEFAULT_LOCAL_MODEL,
        "confidence": 0.9,
        "reason": "padrão local",
        "constraints": Constraints(),
    }
    payload.update(overrides)
    return RouteDecision.model_validate(payload)


def test_request_defaults_to_text_and_pt_br() -> None:
    request = Request(request_id="req-1", text="olá")
    assert request.input_type == "text"
    assert request.language == "pt-BR"


def test_invalid_intent_rejected() -> None:
    with pytest.raises(ValidationError, match="intent"):
        _decision(intent="hacking")


def test_invalid_risk_rejected() -> None:
    with pytest.raises(ValidationError, match="risk"):
        _decision(risk="critical")


def test_allow_cloud_must_be_false() -> None:
    with pytest.raises(ValidationError, match="allow_cloud"):
        Constraints(allow_cloud=True)
    decision = _decision()
    assert decision.constraints.allow_cloud is False


def test_safety_limits_on_constraints() -> None:
    with pytest.raises(ValidationError):
        Constraints(max_steps=0)
    with pytest.raises(ValidationError):
        Constraints(max_steps=9)
    with pytest.raises(ValidationError):
        Constraints(max_tool_calls=-1)
    with pytest.raises(ValidationError, match="max_tool_calls"):
        Constraints(max_steps=2, max_tool_calls=3)
    with pytest.raises(ValidationError):
        Constraints(timeout_seconds=0)
    with pytest.raises(ValidationError):
        Constraints(timeout_seconds=121)


def test_input_type_only_text() -> None:
    with pytest.raises(ValidationError):
        Request(request_id="r1", input_type="audio", text="oi")
    with pytest.raises(ValidationError):
        Request(request_id="r1", input_type="vision", text="oi")


def test_high_risk_and_automation_require_approval() -> None:
    with pytest.raises(ValidationError, match="requires_approval"):
        _decision(risk="high", requires_approval=False)
    with pytest.raises(ValidationError, match="requires_approval"):
        _decision(intent="automation", requires_approval=False)
    ok = _decision(intent="automation", risk="medium", requires_approval=True)
    assert ok.requires_approval is True


def test_router_result_roundtrip() -> None:
    request = Request(request_id="abc", text="escreva um teste")
    decision = _decision(intent="coding", selected_profile="coding")
    result = RouterResult(request=request, decision=decision)
    dumped = result.model_dump()
    restored = RouterResult.model_validate(dumped)
    assert restored.request.request_id == "abc"
    assert restored.decision.intent == "coding"
    assert restored.decision.constraints.allow_cloud is False


def test_model_profile_local_only() -> None:
    with pytest.raises(ValidationError, match="local_only"):
        ModelProfile(
            name="x",
            model=DEFAULT_LOCAL_MODEL,
            intents=("general",),
            local_only=False,
        )


def test_routing_policy_default_is_valid() -> None:
    policy = default_policy()
    assert isinstance(policy, RoutingPolicy)
    assert policy.language == "pt-BR"
    assert policy.constraints.allow_cloud is False
    assert policy.default_model == DEFAULT_LOCAL_MODEL
