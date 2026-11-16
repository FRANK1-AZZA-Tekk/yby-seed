"""Portão de segredos e redação antes da nuvem."""

from __future__ import annotations

import json

from src.engine.budget import CloudBudget
from src.engine.cache import ResponseCache
from src.engine.cloud_usage_log import CloudUsageLog, EVENT_BLOCKED_SENSITIVE, EVENT_COMPLETED
from src.engine.hybrid import HybridEngine
from src.engine.context import TRUNCATION_MARKER, trim_context
from src.engine.providers import (
    CascadingCloudProvider,
    CloudProvider,
    CloudResult,
    ProviderError,
)
from src.engine.secret_gate import (
    find_secret,
    find_secret_in_outbound,
    normalize_for_secret_scan,
    redact_for_cloud,
)
from tests.test_engine import FakeCloud, FakeOllama, _config


class _Resp:
    def __init__(self, status: int, payload: object) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> object:
        return self._payload


class _Session:
    def __init__(self, response: _Resp) -> None:
        self.response = response
        self.posts: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> _Resp:
        self.posts.append({"url": url, **kwargs})
        return self.response


def test_find_secret_sk_or_v1_bare() -> None:
    hit = find_secret("sk-or-v1-abcdefghijklmnopqrstuvwxyz012345")
    assert hit is not None
    assert hit.kind == "api_key"


def test_find_secret_sk_proj() -> None:
    hit = find_secret("usa sk-proj-abcdefghijklmnopqrstuvwxyz0123456789")
    assert hit is not None
    assert hit.kind == "api_key"


def test_find_secret_openrouter_env_line() -> None:
    hit = find_secret("OPENROUTER_API_KEY=sk-or-v1-abcdefghijklmnopqrstuvwxyz012345")
    assert hit is not None
    assert hit.kind == "api_key"


def test_find_secret_xai_and_github() -> None:
    assert find_secret("xai-abcdefghijklmnopqrstuvwxyz").kind == "api_key"
    assert find_secret("ghp_" + ("a" * 36)).kind == "api_key"
    assert find_secret("AKIA" + ("A" * 16)).kind == "api_key"


def test_code_with_loopback_still_allowed() -> None:
    assert find_secret("curl http://127.0.0.1:11434/api/tags") is None


def test_redact_email_keeps_code_context() -> None:
    text = "envie para user@example.com e use 127.0.0.1"
    out = redact_for_cloud(text)
    assert "[EMAIL_REDACTED]" in out
    assert "127.0.0.1" in out
    assert "user@example.com" not in out


def test_heavy_secret_no_http(tmp_path) -> None:
    log = CloudUsageLog(tmp_path / "cloud_usage.jsonl")
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "ask",
            "YBY_CLOUD_LOG_PATH": str(log.path),
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
            "YBY_CLOUD_ALLOW_NO_TTY": "1",
        }
    )
    session = _Session(
        _Resp(200, {"choices": [{"message": {"content": "nao deveria"}}]})
    )
    chain = CascadingCloudProvider(
        CloudProvider(
            "https://openrouter.ai/api/v1",
            api_key="k",
            timeout=2,
            session=session,
        ),
        primary_model="openrouter/free",
    )
    engine = HybridEngine(
        _config(cache_ttl_seconds=0),
        FakeOllama(),
        chain,
        cloud_chain=chain,
        cache=ResponseCache(ttl_seconds=0),
        cloud_log=log,
        budget=budget,
        confirm_fn=lambda _: True,
        has_tty_fn=lambda: True,
    )
    secret = "sk-or-v1-abcdefghijklmnopqrstuvwxyz012345"
    reply = engine.reply(f"pensa mais com {secret}", explicit_heavy=False)
    assert reply.provider == "none"
    assert "sensível" in (reply.notice or "")
    assert session.posts == []
    body = log.path.read_text(encoding="utf-8")
    assert secret not in body
    assert "sk-or-v1" not in body
    row = json.loads(body.strip())
    assert row["result"] == EVENT_BLOCKED_SENSITIVE
    assert row["sensitive_kind"] == "api_key"


def test_blocked_sensitive_no_value_in_log(tmp_path) -> None:
    log = CloudUsageLog(tmp_path / "cloud.jsonl")
    with __import__("pytest").raises(ValueError, match="proibido"):
        log.append(
            {
                "timestamp": 1.0,
                "provider": "openrouter",
                "model": "m",
                "purpose": "t",
                "input_tokens_estimate": 1,
                "output_tokens_estimate": 0,
                "result": EVENT_BLOCKED_SENSITIVE,
                "prompt": "segredo",
            }
        )


def test_cascade_fake_only_complete_still_works() -> None:
    """Duck-type: primary só com complete (sem complete_with_meta)."""

    primary = FakeCloud(text="ok-cloud", api_key="k")
    chain = CascadingCloudProvider(
        primary,  # type: ignore[arg-type]
        primary_model="openrouter/free",
    )
    result = chain.complete_with_meta("pensa mais", system="sys")
    assert isinstance(result, CloudResult)
    assert result.text == "ok-cloud"
    assert primary.calls


def test_find_secret_stripe_anthropic_pem_jwt() -> None:
    assert find_secret("sk_live_" + ("a" * 24)).kind == "api_key"
    assert find_secret("sk_test_" + ("b" * 24)).kind == "api_key"
    assert find_secret("sk-ant-api03-" + ("c" * 20)).kind == "api_key"
    assert find_secret("-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----").kind == (
        "private_key"
    )
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." + ("a" * 20) + "." + ("b" * 20)
    assert find_secret(jwt).kind == "jwt"


def test_authorization_bearer_header_blocked() -> None:
    raw = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123456789"
    assert find_secret(raw) is not None
    assert find_secret(raw).kind == "token"
    redacted = redact_for_cloud(raw)
    assert "abcdefghijklmnopqrstuvwxyz0123456789" not in redacted
    assert "[TOKEN_REDACTED]" in redacted


def test_json_secrets_without_known_prefix_blocked() -> None:
    api = '{"api_key":"notaprefixbutlongsecretvalue12345"}'
    token = '{"token":"abcdefghijklmnopqrstuvwxyz0123456789"}'
    password = '{"password":"supersecretpasswordvalue"}'
    assert find_secret(api).kind == "api_key"
    assert find_secret(token).kind == "token"
    assert find_secret(password).kind == "password"
    assert "notaprefixbutlongsecretvalue12345" not in redact_for_cloud(api)
    assert "abcdefghijklmnopqrstuvwxyz0123456789" not in redact_for_cloud(token)
    assert "supersecretpasswordvalue" not in redact_for_cloud(password)


def test_zwsp_inside_sk_or_v1_still_blocked() -> None:
    raw = "sk-or-v1-\u200babcdefghijklmnopqrstuvwxyz012345"
    assert "\u200b" in raw
    assert find_secret(raw) is not None
    assert find_secret(raw).kind == "api_key"
    assert "\u200b" not in normalize_for_secret_scan(raw)


def test_split_key_across_trim_blocked(tmp_path) -> None:
    """M1: cabeça+cauda reconstitui a chave após remover o marker."""

    prefix = "sk-or-v1-"
    suffix = "abcdefghijklmnopqrstuvwxyz012345"
    max_chars = 120
    keep = max_chars - len(TRUNCATION_MARKER)
    head_len = keep * 2 // 3
    tail_len = keep - head_len
    head_pad = "H" * (head_len - len(prefix))
    tail_pad = "T" * (tail_len - len(suffix))
    # Ruído sem [A-Za-z0-9_-] para o regex não engolir o miolo como sufixo da chave.
    prompt = head_pad + prefix + ("!" * 500) + suffix + tail_pad
    assert find_secret(prompt) is None  # partida no texto completo
    trimmed = trim_context(prompt, max_chars)
    assert TRUNCATION_MARKER in trimmed
    assert trimmed.startswith(head_pad + prefix)
    assert trimmed.endswith(suffix + tail_pad)
    assert find_secret_in_outbound(trimmed) is not None

    log = CloudUsageLog(tmp_path / "cloud_usage.jsonl")
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "ask",
            "YBY_CLOUD_LOG_PATH": str(log.path),
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
        }
    )
    session = _Session(_Resp(200, {"choices": [{"message": {"content": "x"}}]}))
    chain = CascadingCloudProvider(
        CloudProvider(
            "https://openrouter.ai/api/v1",
            api_key="k",
            timeout=2,
            session=session,
        ),
        primary_model="openrouter/free",
    )
    engine = HybridEngine(
        _config(cache_ttl_seconds=0, cloud_max_chars=max_chars),
        FakeOllama(),
        chain,
        cloud_chain=chain,
        cache=ResponseCache(ttl_seconds=0),
        cloud_log=log,
        budget=budget,
        confirm_fn=lambda _: True,
        has_tty_fn=lambda: True,
    )
    reply = engine.reply(prompt, explicit_heavy=True)
    assert reply.provider == "none"
    assert session.posts == []
    assert "sensível" in (reply.notice or "")
    assert prefix not in log.path.read_text(encoding="utf-8")


def test_ollama_fallback_blocks_secret(tmp_path) -> None:
    log = CloudUsageLog(tmp_path / "cloud_usage.jsonl")
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "ask",
            "YBY_CLOUD_LOG_PATH": str(log.path),
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
        }
    )
    session = _Session(_Resp(200, {"choices": [{"message": {"content": "x"}}]}))
    chain = CascadingCloudProvider(
        CloudProvider(
            "https://openrouter.ai/api/v1",
            api_key="k",
            timeout=2,
            session=session,
        ),
        primary_model="openrouter/free",
    )
    secret = "sk-or-v1-abcdefghijklmnopqrstuvwxyz012345"
    engine = HybridEngine(
        _config(cache_ttl_seconds=0),
        FakeOllama(error=ProviderError("down")),
        chain,
        cloud_chain=chain,
        cache=ResponseCache(ttl_seconds=0),
        cloud_log=log,
        budget=budget,
        confirm_fn=lambda _: True,
        has_tty_fn=lambda: True,
    )
    reply = engine.reply(f"oi {secret}")
    assert reply.provider == "none"
    assert session.posts == []
    assert EVENT_BLOCKED_SENSITIVE in log.path.read_text(encoding="utf-8")


def test_email_redacted_in_post_body(tmp_path) -> None:
    log = CloudUsageLog(tmp_path / "cloud_usage.jsonl")
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "ask",
            "YBY_CLOUD_LOG_PATH": str(log.path),
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
        }
    )
    session = _Session(
        _Resp(200, {"choices": [{"message": {"content": "ok"}}], "usage": {}})
    )
    chain = CascadingCloudProvider(
        CloudProvider(
            "https://openrouter.ai/api/v1",
            api_key="k",
            timeout=2,
            session=session,
        ),
        primary_model="openrouter/free",
    )
    engine = HybridEngine(
        _config(cache_ttl_seconds=0),
        FakeOllama(),
        chain,
        cloud_chain=chain,
        cache=ResponseCache(ttl_seconds=0),
        cloud_log=log,
        budget=budget,
        confirm_fn=lambda _: True,
        has_tty_fn=lambda: True,
    )
    reply = engine.reply("pensa mais e avise user@example.com", explicit_heavy=False)
    assert reply.provider == "cloud"
    assert session.posts
    body = session.posts[0]["json"]
    assert isinstance(body, dict)
    messages = body["messages"]
    user_content = messages[1]["content"]
    assert "user@example.com" not in user_content
    assert "[EMAIL_REDACTED]" in user_content


def test_truncation_without_secret_still_works() -> None:
    text = "A" * 100 + "MEIO" + "B" * 100
    out = trim_context(text, 80)
    assert TRUNCATION_MARKER in out
    assert find_secret_in_outbound(out) is None


def test_cloud_warn_still_calls_cloud(tmp_path) -> None:
    log_path = tmp_path / "cloud_usage.jsonl"
    # Uso já acima do aviso, abaixo do teto.
    log_path.write_text(
        json.dumps(
            {
                "timestamp": __import__("time").time(),
                "provider": "openrouter",
                "model": "m",
                "purpose": "seed",
                "input_tokens_estimate": 160_000,
                "output_tokens_estimate": 0,
                "result": EVENT_COMPLETED,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    log = CloudUsageLog(log_path)
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "ask",
            "YBY_CLOUD_LOG_PATH": str(log_path),
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
            "YBY_CLOUD_WARN_TOKEN_LIMIT": "150000",
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "200000",
        }
    )
    cloud = FakeCloud(api_key="k")
    engine = HybridEngine(
        _config(cache_ttl_seconds=0),
        FakeOllama(),
        cloud,
        cache=ResponseCache(ttl_seconds=0),
        cloud_log=log,
        budget=budget,
        confirm_fn=lambda _: True,
        has_tty_fn=lambda: True,
    )
    reply = engine.reply("oi", explicit_heavy=True)
    assert reply.provider == "cloud"
    assert cloud.calls
    assert reply.notice is not None
    assert reply.notice.startswith("Aviso:")
