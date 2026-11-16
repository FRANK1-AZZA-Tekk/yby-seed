"""Testes do registry de modelos locais."""

from __future__ import annotations

import pytest

from src.router.errors import ConfigurationError, ModelNotFoundError, SafetyViolationError
from src.router.registry import ModelEntry, ModelRegistry, validate_model_entry


def test_default_registry_has_required_roles() -> None:
    registry = ModelRegistry.default()
    roles = set(registry.list_roles())
    assert roles == {"general", "coder", "fallback", "embeddings"}
    assert registry.get("general").model == "qwen3-8b-instruct"
    assert registry.get("coder").model == "qwen2.5-coder-7b-instruct"
    assert registry.get("fallback").model == "qwen3-4b-instruct"
    assert registry.get("embeddings").model == "nomic-embed-text"


def test_each_entry_has_required_fields() -> None:
    registry = ModelRegistry.default()
    for role in registry.list_roles():
        entry = registry.get(role)  # type: ignore[arg-type]
        assert entry.provider in {"ollama", "local"}
        assert entry.model
        assert entry.role == role
        assert entry.context >= 1
        assert entry.max_tokens >= 0
        assert entry.timeout > 0
        assert entry.enabled is True
        assert entry.allow_cloud is False


def test_lookup_by_model_and_intent() -> None:
    registry = ModelRegistry.default()
    assert registry.get_by_model("qwen2.5-coder-7b-instruct").role == "coder"
    assert registry.primary_for_intent("coding").role == "coder"
    assert registry.primary_for_intent("knowledge").role == "general"


def test_invalid_model_returns_error() -> None:
    registry = ModelRegistry.default()
    with pytest.raises(ModelNotFoundError, match="não encontrado"):
        registry.get_by_model("gpt-cloud-secret")
    with pytest.raises(ModelNotFoundError, match="role"):
        registry.get("vision")  # type: ignore[arg-type]


def test_uncensored_primary_blocked() -> None:
    with pytest.raises(SafetyViolationError, match="uncensored"):
        validate_model_entry(
            ModelEntry(
                role="general",
                provider="ollama",
                model="llama-uncensored",
                context=4096,
                max_tokens=512,
                timeout=30.0,
                is_agent_primary=True,
            )
        )


def test_allow_cloud_and_unknown_tools_blocked() -> None:
    with pytest.raises(SafetyViolationError, match="allow_cloud"):
        validate_model_entry(
            ModelEntry(
                role="general",
                provider="ollama",
                model="qwen3-8b-instruct",
                context=4096,
                max_tokens=512,
                timeout=30.0,
                allow_cloud=True,
                is_agent_primary=True,
            )
        )
    with pytest.raises(SafetyViolationError, match="fora do registry"):
        validate_model_entry(
            ModelEntry(
                role="general",
                provider="ollama",
                model="qwen3-8b-instruct",
                context=4096,
                max_tokens=512,
                timeout=30.0,
                allowed_tools=frozenset({"shell_run"}),
                is_agent_primary=True,
            )
        )


def test_invalid_timeout_config() -> None:
    with pytest.raises(ConfigurationError, match="timeout"):
        validate_model_entry(
            ModelEntry(
                role="fallback",
                provider="local",
                model="qwen3-4b-instruct",
                context=1024,
                max_tokens=128,
                timeout=0,
            )
        )
