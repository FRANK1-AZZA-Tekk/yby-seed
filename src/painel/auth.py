"""Auth do painel (token separado do gateway MQTT)."""

from __future__ import annotations

import os
from collections.abc import Mapping


def painel_token_from_env() -> str:
    return (os.environ.get("YBY_PAINEL_TOKEN") or "").strip()


def check_token(headers: Mapping[str, str], expected: str) -> tuple[bool, int, str]:
    """Confere Authorization: Bearer ou X-API-Token."""

    if not expected:
        return False, 503, "YBY_PAINEL_TOKEN não configurado"

    lowered = {key.lower(): value for key, value in headers.items()}
    header = lowered.get("authorization", "")
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
    else:
        token = lowered.get("x-api-token", "").strip()

    if token != expected:
        return False, 401, "token inválido"
    return True, 200, "ok"
