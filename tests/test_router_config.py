"""Testes da configuração central do roteador offline."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.router.config import (
    DEFAULT_LOCAL_MODEL,
    RouterConfig,
    default_constraints,
    default_policy,
)
from src.router.errors import ConfigurationError, ModelNotFoundError, SafetyViolationError
from src.router.schemas import Constraints


def test_default_config_is_valid() -> None:
    config = RouterConfig.default()
    assert config.language == "pt-BR"
    assert config.default_model == DEFAULT_LOCAL_MODEL
    assert config.fallback_model == DEFAULT_LOCAL_MODEL
    assert config.allow_cloud is False
    assert config.max_steps == 8
    assert config.max_tool_calls == 4
    assert config.timeout_seconds == 120.0
    assert len(config.policy.profiles) == 4
    assert config.policy.intents == ("general", "coding", "knowledge", "automation")


def test_default_policy_allow_cloud_false() -> None:
    policy = default_policy()
    assert policy.constraints.allow_cloud is False
    constraints = default_constraints()
    assert constraints.allow_cloud is False


def test_from_env_rejects_allow_cloud_true() -> None:
    with pytest.raises(ConfigurationError, match="YBY_ROUTER_ALLOW_CLOUD"):
        RouterConfig.from_env({"YBY_ROUTER_ALLOW_CLOUD": "true"})


def test_from_env_accepts_explicit_false() -> None:
    config = RouterConfig.from_env({"YBY_ROUTER_ALLOW_CLOUD": "false"})
    assert config.allow_cloud is False


def test_from_env_invalid_max_steps_message() -> None:
    with pytest.raises(ConfigurationError, match="YBY_ROUTER_MAX_STEPS"):
        RouterConfig.from_env({"YBY_ROUTER_MAX_STEPS": "0"})


def test_from_env_invalid_timeout_message() -> None:
    with pytest.raises(ConfigurationError, match="YBY_ROUTER_TIMEOUT_SECONDS"):
        RouterConfig.from_env({"YBY_ROUTER_TIMEOUT_SECONDS": "abc"})


def test_from_env_tool_calls_above_steps() -> None:
    with pytest.raises(ConfigurationError, match="YBY_ROUTER_MAX_TOOL_CALLS"):
        RouterConfig.from_env(
            {
                "YBY_ROUTER_MAX_STEPS": "2",
                "YBY_ROUTER_MAX_TOOL_CALLS": "5",
            }
        )


def test_safety_limits_enforced() -> None:
    config = RouterConfig.default()
    with pytest.raises(SafetyViolationError, match="max_steps"):
        config.enforce_safety(
            intent="general",
            risk="low",
            requires_approval=False,
            max_steps=0,
        )
    with pytest.raises(SafetyViolationError, match="max_tool_calls"):
        config.enforce_safety(
            intent="general",
            risk="low",
            requires_approval=False,
            max_steps=2,
            max_tool_calls=5,
        )
    with pytest.raises(SafetyViolationError, match="timeout_seconds"):
        config.enforce_safety(
            intent="general",
            risk="low",
            requires_approval=False,
            timeout_seconds=999.0,
        )


def test_safety_blocks_cloud_and_unapproved_high_risk() -> None:
    config = RouterConfig.default()
    with pytest.raises(SafetyViolationError, match="allow_cloud"):
        config.enforce_safety(
            intent="general",
            risk="low",
            requires_approval=False,
            allow_cloud=True,
        )
    with pytest.raises(SafetyViolationError, match="high"):
        config.enforce_safety(
            intent="general",
            risk="high",
            requires_approval=False,
        )


def test_missing_profile_raises_model_not_found() -> None:
    config = RouterConfig.default()
    with pytest.raises(ModelNotFoundError, match="perfil não encontrado"):
        config.get_profile("cloud-gpt")


def test_constraints_reject_allow_cloud_true() -> None:
    with pytest.raises(ValidationError, match="allow_cloud"):
        Constraints(allow_cloud=True)


def test_from_policy_rejects_cloud() -> None:
    policy = default_policy()
    # Bypass Constraints validator by constructing via model_construct.
    bad = policy.model_copy(
        update={"constraints": Constraints.model_construct(allow_cloud=True)}
    )
    with pytest.raises(ConfigurationError, match="allow_cloud"):
        RouterConfig.from_policy(bad)
