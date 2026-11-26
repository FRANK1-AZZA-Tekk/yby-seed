"""Privacy Gate fail-closed: impede egresso de dados privados para nuvem."""

from __future__ import annotations

import re
from collections.abc import Callable

from src.security.cloud_sanitizer import sanitize_for_cloud
from src.yby.routing.schemas import (
    ALL_TIERS,
    LOCAL_TIERS,
    PrivacyGateDecision,
    RouteRequest,
)

PRIVATE_ORIGINS: frozenset[str] = frozenset(
    {
        "pgvector",
        "personal_memory",
        "mqtt_telemetry",
        "raw_audio",
        "pix_commercial",
        "rea_artifact",
    }
)

_PRIVATE_METADATA_FLAGS: tuple[str, ...] = (
    "contains_pgvector",
    "vault_context",
    "personal_history",
    "raw_audio",
    "mqtt_payload",
    "pix_data",
    "rea_output",
)

# Sinais de dados comerciais/Pix brasileiros que nunca devem sair para nuvem.
_PIX_COMMERCIAL_PATTERN = re.compile(
    r"\b(?:chave\s+pix|copia\s+e\s+cola|000201|br\.gov\.bcb\.pix|comprovante\s+pix|faturamento\s+interno)\b",
    re.IGNORECASE,
)

ExtraPrivacyGuard = Callable[[RouteRequest], tuple[bool, str | None]]


class PrivacyGate:
    """Portão determinístico de privacidade local-first.

    Qualquer payload privado, de origem local sensível, ou contendo segredos/PII
    ou dados comerciais/Pix é mantido estritamente nos nós locais (`LOCAL_TIERS`).
    """

    def __init__(self, *, extra_guard: ExtraPrivacyGuard | None = None) -> None:
        self._extra_guard = extra_guard

    def evaluate(self, request: RouteRequest) -> PrivacyGateDecision:
        reasons: list[str] = []

        if request.sensitivity == "private":
            reasons.append("sensitivity=private")

        if request.origin in PRIVATE_ORIGINS:
            reasons.append(f"origin={request.origin}")

        for flag in _PRIVATE_METADATA_FLAGS:
            if request.metadata.get(flag):
                reasons.append(f"metadata:{flag}")

        if _PIX_COMMERCIAL_PATTERN.search(request.prompt):
            reasons.append("pix_commercial_pattern")

        # Força o sanitizador sempre ativo para inspeção, independente de env debug.
        sanitized = sanitize_for_cloud(
            request.prompt,
            environ={"YBY_CLOUD_SANITIZE": "1"},
        )
        if sanitized.redactions > 0:
            types_str = ",".join(sorted(sanitized.by_type.keys()))
            reasons.append(f"sensitive_content_detected:{types_str}")

        if self._extra_guard is not None:
            allowed_by_extra, extra_reason = self._extra_guard(request)
            if not allowed_by_extra:
                reasons.append(extra_reason or "extra_guard_denied")

        if reasons:
            return PrivacyGateDecision(
                allow_cloud=False,
                effective_sensitivity="private",
                blocked_reasons=tuple(reasons),
                allowed_tiers=LOCAL_TIERS,
                redaction_count=sanitized.redactions,
                redacted_types=dict(sanitized.by_type),
                sanitized_prompt=sanitized.text,
            )

        return PrivacyGateDecision(
            allow_cloud=True,
            effective_sensitivity="public",
            blocked_reasons=(),
            allowed_tiers=ALL_TIERS,
            redaction_count=0,
            redacted_types={},
            sanitized_prompt=sanitized.text,
        )
