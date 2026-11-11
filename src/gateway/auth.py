"""Token do gateway. Rotas de dados ficam fechadas sem ele."""

from __future__ import annotations

from collections.abc import Mapping


def check_token(headers: Mapping[str, str], expected: str) -> tuple[bool, int, str]:
    """Confere Authorization: Bearer ou X-API-Token."""

    if not expected:
        return False, 503, "GATEWAY_TOKEN não configurado"

    lowered = {key.lower(): value for key, value in headers.items()}
    header = lowered.get("authorization", "")
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
    else:
        token = lowered.get("x-api-token", "").strip()

    if token != expected:
        return False, 401, "token inválido"
    return True, 200, "ok"
