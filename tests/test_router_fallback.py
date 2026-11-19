"""Testes da política de fallback local."""

from __future__ import annotations

import time

import pytest

from src.router.errors import SafetyViolationError
from src.router.fallback import FallbackError, FallbackPolicy
from src.router.registry import ModelEntry, ModelRegistry


def _ok_invoker(entry: ModelEntry, prompt: str) -> str:
    return f"{entry.model}::{prompt}"


def _fail_primary_ok_fallback(entry: ModelEntry, prompt: str) -> str:
    if entry.role == "fallback":
        return f"fb::{prompt}"
    raise RuntimeError("primary down")


def _always_fail(entry: ModelEntry, prompt: str) -> str:
    raise RuntimeError(f"down:{entry.model}")


def _slow_invoker(entry: ModelEntry, prompt: str) -> str:
    time.sleep(entry.timeout + 0.05)
    return "late"


def test_primary_success_no_fallback() -> None:
    registry = ModelRegistry.default()
    policy = FallbackPolicy(registry=registry, max_retries=0)
    primary = registry.get("coder")
    result = policy.execute(primary=primary, prompt="oi", invoker=_ok_invoker)
    assert result.used_fallback is False
    assert result.selected_model == primary.model
    assert result.fallback_reason is None
    assert "qwen2.5-coder-7b-instruct" in result.text


def test_fallback_used_when_primary_fails() -> None:
    registry = ModelRegistry.default()
    policy = FallbackPolicy(registry=registry, max_retries=0)
    primary = registry.get("general")
    result = policy.execute(
        primary=primary,
        prompt="ajuda",
        invoker=_fail_primary_ok_fallback,
    )
    assert result.used_fallback is True
    assert result.fallback_model == "qwen3-4b-instruct"
    assert result.selected_model == "qwen3-4b-instruct"
    assert result.fallback_reason is not None
    assert "primary_failed" in result.fallback_reason
    assert "nuvem" not in result.text.casefold()


def test_fallback_never_uses_cloud() -> None:
    registry = ModelRegistry.default()
    cloudish = ModelEntry(
        role="general",
        provider="ollama",
        model="qwen3-8b-instruct",
        context=8192,
        max_tokens=1024,
        timeout=10.0,
        allow_cloud=True,
        is_agent_primary=True,
    )
    # Bypass validate by constructing registry manually after monkeypatch?
    # validate happens on register; build policy with local registry and
    # assert execute rejects allow_cloud primary.
    policy = FallbackPolicy(registry=registry, max_retries=0)
    with pytest.raises(SafetyViolationError, match="allow_cloud"):
        policy.execute(primary=cloudish, prompt="x", invoker=_ok_invoker)


def test_both_fail_returns_safe_error() -> None:
    registry = ModelRegistry.default()
    policy = FallbackPolicy(registry=registry, max_retries=0)
    with pytest.raises(FallbackError, match="nuvem bloqueada"):
        policy.execute(
            primary=registry.get("general"),
            prompt="x",
            invoker=_always_fail,
        )


def test_timeout_is_respected() -> None:
    registry = ModelRegistry.default()
    policy = FallbackPolicy(
        registry=registry,
        max_retries=0,
        overall_timeout_seconds=0.2,
    )
    primary = ModelEntry(
        role="general",
        provider="ollama",
        model="qwen3-8b-instruct",
        context=8192,
        max_tokens=512,
        timeout=0.05,
        is_agent_primary=True,
    )
    with pytest.raises((FallbackError, TimeoutError)):
        # Primary times out; fallback also slow → exhausted/timeout.
        policy.execute(primary=primary, prompt="x", invoker=_slow_invoker)


def test_retries_limited() -> None:
    registry = ModelRegistry.default()
    calls: list[str] = []

    def counting(entry: ModelEntry, prompt: str) -> str:
        calls.append(entry.model)
        raise RuntimeError("fail")

    policy = FallbackPolicy(registry=registry, max_retries=2)
    with pytest.raises(FallbackError):
        policy.execute(
            primary=registry.get("coder"),
            prompt="x",
            invoker=counting,
        )
    # 3 primary attempts (0..2) + 1 fallback
    primary_calls = [c for c in calls if c == "qwen2.5-coder-7b-instruct"]
    assert len(primary_calls) == 3
    assert "qwen3-4b-instruct" in calls
