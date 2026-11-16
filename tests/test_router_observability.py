"""Testes de observabilidade estruturada do roteador."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.router.errors import SafetyViolationError
from src.router.observability import (
    RouterObserver,
    contains_secret,
    estimate_cost_local,
    estimate_tokens,
    redact_secrets,
    sanitize_log_payload,
)


def test_structured_event_fields(tmp_path: Path) -> None:
    log_path = tmp_path / "router.jsonl"
    observer = RouterObserver(path=log_path)
    event = observer.record(
        request_id="req-1",
        intent="coding",
        selected_model="qwen2.5-coder-7b-instruct",
        fallback_used=True,
        fallback_model="qwen3-4b-instruct",
        latency_ms=12.5,
        tokens=40,
        cost=0.0,
        approval_required=False,
        outcome="fallback_success",
        reason="primary_failed:timeout",
    )
    assert event.request_id == "req-1"
    assert event.timestamp > 0
    assert event.intent == "coding"
    assert event.selected_model == "qwen2.5-coder-7b-instruct"
    assert event.fallback_used is True
    assert event.fallback_model == "qwen3-4b-instruct"
    assert event.latency_ms == 12.5
    assert event.tokens == 40
    assert event.cost == 0.0
    assert event.approval_required is False
    assert event.outcome == "fallback_success"
    assert len(observer.events) == 1
    raw = log_path.read_text(encoding="utf-8")
    assert "req-1" in raw
    assert "api_key" not in raw


def test_no_secrets_in_logs() -> None:
    dirty = "authorization: Bearer sk-abcdef123456 password=segredo"
    clean = redact_secrets(dirty)
    assert "sk-abcdef" not in clean
    assert "segredo" not in clean
    assert "[REDACTED]" in clean
    assert contains_secret(dirty) is True
    assert contains_secret("intent=coding; allow_cloud=false") is False


def test_forbidden_fields_rejected() -> None:
    with pytest.raises(SafetyViolationError, match="campo proibido"):
        sanitize_log_payload({"request_id": "1", "api_key": "secret"})
    with pytest.raises(SafetyViolationError, match="campo proibido"):
        sanitize_log_payload({"prompt": "texto do usuário"})


def test_tokens_and_local_cost() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 40) == 10
    assert estimate_cost_local(tokens=1000) == 0.0


def test_reason_is_redacted_on_record() -> None:
    observer = RouterObserver()
    event = observer.record(
        request_id="req-2",
        intent="general",
        selected_model="qwen3-8b-instruct",
        fallback_used=False,
        fallback_model=None,
        latency_ms=1.0,
        tokens=None,
        cost=0.0,
        approval_required=True,
        outcome="success",
        reason="falha com api_key=sk-abcdef1234567890",
    )
    assert "sk-abcdef" not in event.reason
    assert event.approval_required is True
