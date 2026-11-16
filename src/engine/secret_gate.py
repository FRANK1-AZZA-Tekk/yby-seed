"""Bloqueio e redação de segredos antes da nuvem.

Hard-block (fail-closed): chave, senha, token, CPF e CNPJ.
Redação defensiva: e-mail e restos de credencial sem bloquear o pedido.
IP, path e telefone ficam de fora — falso positivo em código.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Ordem: o primeiro match decide o tipo reportado no bloqueio.
_CHECKS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "api_key",
        re.compile(
            r"("
            r"sk-or-v1-[A-Za-z0-9_-]{16,}"
            r"|sk-proj-[A-Za-z0-9_-]{16,}"
            r"|sk-[A-Za-z0-9]{20,}"
            r"|xai-[A-Za-z0-9_-]{16,}"
            r"|ghp_[A-Za-z0-9]{20,}"
            r"|AKIA[0-9A-Z]{16}"
            r"|api[_-]?key[_-]?[=:]\s*[A-Za-z0-9._-]{16,}"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "password",
        re.compile(r"(password|senha|passwd)\s*[=:]\s*\S+", re.IGNORECASE),
    ),
    (
        "token",
        re.compile(r"(token|bearer)\s*[=:]\s*[A-Za-z0-9._-]{20,}", re.IGNORECASE),
    ),
    ("cpf", re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")),
    ("cnpj", re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")),
)

_REDACT: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("email", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[EMAIL_REDACTED]"),
    (
        "api_key",
        re.compile(
            r"("
            r"sk-or-v1-[A-Za-z0-9_-]{16,}"
            r"|sk-proj-[A-Za-z0-9_-]{16,}"
            r"|sk-[A-Za-z0-9]{20,}"
            r"|xai-[A-Za-z0-9_-]{16,}"
            r"|ghp_[A-Za-z0-9]{20,}"
            r"|AKIA[0-9A-Z]{16}"
            r"|api[_-]?key[_-]?[=:]\s*[A-Za-z0-9._-]{16,}"
            r")",
            re.IGNORECASE,
        ),
        "[API_KEY_REDACTED]",
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
    ("cpf", re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "[CPF_REDACTED]"),
    ("cnpj", re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"), "[CNPJ_REDACTED]"),
)


@dataclass(frozen=True)
class SecretFinding:
    """Tipo detectado. Nunca carrega o valor casado."""

    kind: str


def find_secret(text: str) -> SecretFinding | None:
    """Devolve o primeiro tipo sensível ou None. Sem o trecho casado."""

    for kind, pattern in _CHECKS:
        if pattern.search(text):
            return SecretFinding(kind)
    return None


def redact_for_cloud(text: str) -> str:
    """Redige padrões sensíveis sem registrar o valor original."""

    out = text
    for _kind, pattern, replacement in _REDACT:
        out = pattern.sub(replacement, out)
    return out
