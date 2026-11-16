"""Bloqueio e redação de segredos antes da nuvem.

Hard-block (fail-closed): chave, senha, token, PEM, JWT, CPF e CNPJ.
Redação defensiva: e-mail e restos de credencial sem bloquear o pedido.
IP, path e telefone ficam de fora — falso positivo em código.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from src.engine.context import TRUNCATION_MARKER

# Ordem: o primeiro match decide o tipo reportado no bloqueio.
_CHECKS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "api_key",
        re.compile(
            r"("
            r"sk-or-v1-[A-Za-z0-9_-]{16,}"
            r"|sk-proj-[A-Za-z0-9_-]{16,}"
            r"|sk-ant-[A-Za-z0-9_-]{16,}"
            r"|sk_live_[A-Za-z0-9]{16,}"
            r"|sk_test_[A-Za-z0-9]{16,}"
            r"|sk-[A-Za-z0-9]{20,}"
            r"|xai-[A-Za-z0-9_-]{16,}"
            r"|ghp_[A-Za-z0-9]{20,}"
            r"|AKIA[0-9A-Z]{16}"
            r"|[A-Za-z0-9_]*API[_-]?KEY\s*[=:]\s*\S{8,}"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
            re.IGNORECASE,
        ),
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
    (
        "password",
        re.compile(r"(password|senha|passwd)\s*[=:]\s*\S+", re.IGNORECASE),
    ),
    (
        "token",
        re.compile(r"(token|bearer)\s*[=:]\s*[A-Za-z0-9._-]{20,}", re.IGNORECASE),
    ),
    ("cpf", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("cnpj", re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")),
)

_REDACT: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("email", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[EMAIL_REDACTED]"),
    (
        "api_key",
        re.compile(
            r"("
            r"sk-or-v1-[A-Za-z0-9_-]{16,}"
            r"|sk-proj-[A-Za-z0-9_-]{16,}"
            r"|sk-ant-[A-Za-z0-9_-]{16,}"
            r"|sk_live_[A-Za-z0-9]{16,}"
            r"|sk_test_[A-Za-z0-9]{16,}"
            r"|sk-[A-Za-z0-9]{20,}"
            r"|xai-[A-Za-z0-9_-]{16,}"
            r"|ghp_[A-Za-z0-9]{20,}"
            r"|AKIA[0-9A-Z]{16}"
            r"|[A-Za-z0-9_]*API[_-]?KEY\s*[=:]\s*\S{8,}"
            r")",
            re.IGNORECASE,
        ),
        "[API_KEY_REDACTED]",
    ),
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
            r".*?"
            r"-----END (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
            re.IGNORECASE | re.DOTALL,
        ),
        "[PRIVATE_KEY_REDACTED]",
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "[JWT_REDACTED]",
    ),
    (
        "password",
        re.compile(r"((?:password|senha|passwd)\s*[=:]\s*)\S+", re.IGNORECASE),
        r"\1[PASSWORD_REDACTED]",
    ),
    (
        "token",
        re.compile(r"((?:token|bearer)\s*[=:]\s*)[A-Za-z0-9._-]{20,}", re.IGNORECASE),
        r"\1[TOKEN_REDACTED]",
    ),
    ("cpf", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF_REDACTED]"),
    ("cnpj", re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"), "[CNPJ_REDACTED]"),
)

# Cf / Mn (não espaçadores) + ZWSP / BOM / etc.
_FORMAT_CHARS = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff\u00ad"), None)


@dataclass(frozen=True)
class SecretFinding:
    """Tipo detectado. Nunca carrega o valor casado."""

    kind: str


def normalize_for_secret_scan(text: str) -> str:
    """NFC + remove caracteres de formato / zero-width usados para evasão."""

    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.translate(_FORMAT_CHARS)
    # Remove outras marcas de formato Unicode (categoria Cf).
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Cf")


def find_secret(text: str) -> SecretFinding | None:
    """Devolve o primeiro tipo sensível ou None. Sem o trecho casado."""

    scanned = normalize_for_secret_scan(text)
    for kind, pattern in _CHECKS:
        if pattern.search(scanned):
            return SecretFinding(kind)
    return None


def find_secret_in_outbound(trimmed: str) -> SecretFinding | None:
    """Escaneia o texto pós-trim e a junção head+tail (anti-split no marker)."""

    hit = find_secret(trimmed)
    if hit is not None:
        return hit
    if TRUNCATION_MARKER in trimmed:
        joined = trimmed.replace(TRUNCATION_MARKER, "")
        return find_secret(joined)
    return None


def redact_for_cloud(text: str) -> str:
    """Redige padrões sensíveis sem registrar o valor original."""

    out = normalize_for_secret_scan(text)
    for _kind, pattern, replacement in _REDACT:
        out = pattern.sub(replacement, out)
    return out
