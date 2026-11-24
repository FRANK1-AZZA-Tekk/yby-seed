"""T9 / S4: sanitizer de egresso para nuvem (#42)."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from src.engine.budget import CloudBudget
from src.engine.cloud_usage_log import CloudUsageLog
from src.engine.config import EngineConfig
from src.engine.hybrid import HybridEngine
from src.engine.routing import DEFAULT_HEAVY_PHRASES
from src.security.cloud_sanitizer import sanitize_enabled, sanitize_for_cloud


def _config() -> EngineConfig:
    return EngineConfig(
        ollama_base_url="http://ollama.test",
        local_model="qwen2.5-coder:3b",
        cloud_base_url="https://openrouter.ai/api/v1",
        cloud_model="openrouter/free",
        cloud_api_key="test-key",
        cloud_fallback_base_url="https://api.x.ai/v1",
        cloud_fallback_model="grok-4.7",
        cloud_fallback_api_key="",
        heavy_min_chars=1200,
        heavy_min_lines=25,
        heavy_min_questions=3,
        heavy_phrases=DEFAULT_HEAVY_PHRASES,
        ollama_timeout=5.0,
        cloud_timeout=5.0,
        cache_ttl_seconds=0.0,
        cloud_max_chars=12000,
        cloud_max_output_tokens=512,
    )


class FakeOllama:
    def complete(self, prompt: str, *, model: str, system: str) -> str:
        return "local"


class CapturingCloud:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def has_credentials(self) -> bool:
        return True

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        self.calls.append(prompt)
        return "ok-from-cloud"


def test_sanitize_strips_secrets_email_and_bearer() -> None:
    raw = (
        "OPENROUTER_API_KEY=sk-abcdefghijklmnopqrstuvwxyz012345 "
        "user@empresa.com.br Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abcde "
        "CPF 123.456.789-09"
    )
    result = sanitize_for_cloud(raw)
    assert result.enabled is True
    assert result.redactions >= 3
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in result.text
    assert "user@empresa.com.br" not in result.text
    assert "eyJhbGciOi" not in result.text
    assert "123.456.789-09" not in result.text
    assert "[EMAIL_REDACTED]" in result.text
    assert "[CPF_REDACTED]" in result.text


def test_sanitize_counts_multiple_secrets_individually() -> None:
    raw = (
        "api_key=sk-abcdefghijklmnopqrstuvwxyz012345 "
        "token=abcdef1234567890abcdef "
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abcde"
    )

    result = sanitize_for_cloud(raw)

    assert result.enabled is True
    assert result.by_type["secret"] == 3
    assert result.redactions >= 3
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in result.text
    assert "abcdef1234567890abcdef" not in result.text
    assert "eyJhbGciOi" not in result.text


def test_sanitize_counts_zero_when_no_sensitive_data() -> None:
    raw = "Configure o GPIO18 como saída e aguarde 500 ms."

    result = sanitize_for_cloud(raw)

    assert result.enabled is True
    assert result.redactions == 0
    assert result.by_type == {}
    assert result.text == raw


def test_sanitize_can_be_disabled_via_env() -> None:
    assert sanitize_enabled({"YBY_CLOUD_SANITIZE": "0"}) is False
    raw = "OPENROUTER_API_KEY=sk-abcdefghijklmnopqrstuvwxyz012345"
    result = sanitize_for_cloud(raw, environ={"YBY_CLOUD_SANITIZE": "0"})
    assert result.enabled is False
    assert "sk-abcdefghijklmnopqrstuvwxyz" in result.text


def test_hybrid_cloud_egress_redacts_before_http() -> None:
    """Regressão do bug: segredos/PII chegavam crus em cloud.complete."""

    with TemporaryDirectory() as td:
        log = Path(td) / "cloud.jsonl"
        cloud = CapturingCloud()
        engine = HybridEngine(
            _config(),
            FakeOllama(),
            cloud,
            cloud_log=CloudUsageLog(log),
            budget=CloudBudget.from_env(
                {
                    "YBY_CLOUD_MODE": "ask",
                    "YBY_CLOUD_REQUIRE_CONFIRM": "0",
                    "YBY_CLOUD_LOG_PATH": str(log),
                }
            ),
            confirm_fn=lambda _m: True,
            has_tty_fn=lambda: True,
        )
        secret_prompt = (
            "pensa mais: OPENROUTER_API_KEY=sk-abcdefghijklmnopqrstuvwxyz012345 "
            "email user@empresa.com.br Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abcde"
        )
        reply = engine.reply(secret_prompt)
        assert reply.provider == "cloud"
        assert len(cloud.calls) == 1
        outbound = cloud.calls[0]
        assert "sk-abcdefghijklmnopqrstuvwxyz" not in outbound
        assert "user@empresa.com.br" not in outbound
        assert "eyJhbGciOi" not in outbound
        assert reply.notice is not None
        assert "redactado" in reply.notice.casefold() or "redact" in reply.notice.casefold()
