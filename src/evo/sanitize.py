"""Sanitização de texto/payloads antes de persistir (sem segredos)."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|bearer|secret|"
        r"password|passwd|token|authorization)\b\s*[:=]\s*['\"]?([^\s'\"]+)"
    ),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bxai-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bOR_[A-Za-z0-9]{16,}\b"),
    re.compile(
        r"(?i)\b((?:YBY_|OPENROUTER_|XAI_|OPENAI_|ANTHROPIC_|AWS_|GITHUB_)?"
        r"(?:API_KEY|TOKEN|SECRET|PASSWORD|PASSWD))\s*=\s*([^\s]+)"
    ),
)

_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "auth_token",
        "authorization",
        "bearer",
        "password",
        "passwd",
        "secret",
        "token",
        "openai_api_key",
        "openrouter_api_key",
        "xai_api_key",
        "yby_cloud_api_key",
        "yby_grok_api_key",
    }
)


def sanitize_text(text: str) -> str:
    """Remove valores de segredos em texto livre."""

    if not text:
        return text
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub(_replace_match, out)
    return out


def _replace_match(match: re.Match[str]) -> str:
    groups = match.groups()
    if len(groups) >= 2 and groups[0] is not None:
        return f"{groups[0]}={REDACTED}"
    return REDACTED


def sanitize_value(value: Any) -> Any:
    """Recursivo: dict/list/str; chaves proibidas viram REDACTED."""

    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if key_str.casefold().replace("-", "_") in _FORBIDDEN_KEYS:
                cleaned[key_str] = REDACTED
            else:
                cleaned[key_str] = sanitize_value(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_value(item) for item in value)
    return value
