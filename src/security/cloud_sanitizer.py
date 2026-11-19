"""Sanitização de prompts antes de egresso para nuvem (CLOUD_USAGE_SPEC §S4).

Sucessor estável de `openrouter_sanitizer.py`: API pura (sem side effects de log),
redação de segredos/PII e contagem por tipo para telemetria local.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from src.evo.sanitize import sanitize_text as _sanitize_secrets

# PII / identificadores além dos segredos já cobertos por evo.sanitize.
_PII_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "email",
        re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "[EMAIL_REDACTED]",
    ),
    (
        "cpf",
        re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
        "[CPF_REDACTED]",
    ),
    (
        "cnpj",
        re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"),
        "[CNPJ_REDACTED]",
    ),
    (
        "phone",
        re.compile(
            r"(?:\+\d{1,3}[\s-]?)?\(?\d{2}\)?[\s-]?\d{4,5}[\s-]?\d{4}\b"
        ),
        "[PHONE_REDACTED]",
    ),
    (
        "ipv4",
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        ),
        "[IP_REDACTED]",
    ),
    (
        "abs_unix_path",
        re.compile(r"(?<![\w.-])(/(?:home|Users|root|var|opt|etc)/[^\s\"']+)"),
        "[PATH_REDACTED]",
    ),
    (
        "abs_windows_path",
        re.compile(r"\b[A-Za-z]:\\[^\s\"']+"),
        "[PATH_REDACTED]",
    ),
)


@dataclass(frozen=True)
class SanitizeResult:
    """Texto pronto para HTTP + contagem de redações."""

    text: str
    redactions: int
    by_type: dict[str, int]
    enabled: bool


def sanitize_enabled(environ: dict[str, str] | None = None) -> bool:
    """YBY_CLOUD_SANITIZE=0 desliga o gate (debug apenas; padrão ligado)."""

    source = environ if environ is not None else os.environ
    raw = source.get("YBY_CLOUD_SANITIZE", "1").strip().casefold()
    if not raw:
        return True
    return raw not in {"0", "false", "no", "off", "nao", "não"}


def sanitize_for_cloud(
    text: str,
    *,
    environ: dict[str, str] | None = None,
) -> SanitizeResult:
    """Redige segredos e PII antes de enviar o prompt à nuvem."""

    if not text:
        return SanitizeResult(text="", redactions=0, by_type={}, enabled=True)
    if not sanitize_enabled(environ):
        return SanitizeResult(text=text, redactions=0, by_type={}, enabled=False)

    by_type: dict[str, int] = {}
    # Segredos primeiro (API keys, bearer, env vars).
    before_secrets = text
    out = _sanitize_secrets(text)
    if out != before_secrets:
        by_type["secret"] = 1

    for name, pattern, replacement in _PII_PATTERNS:
        matches = pattern.findall(out)
        if not matches:
            continue
        out = pattern.sub(replacement, out)
        by_type[name] = by_type.get(name, 0) + len(matches)

    redactions = sum(by_type.values())
    return SanitizeResult(text=out, redactions=redactions, by_type=by_type, enabled=True)
