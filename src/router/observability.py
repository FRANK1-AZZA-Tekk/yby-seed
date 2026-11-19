"""Observabilidade estruturada do roteador offline (sem segredos)."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

from src.router.errors import SafetyViolationError

Outcome = Literal["success", "fallback_success", "error", "timeout", "blocked"]

FORBIDDEN_LOG_KEYS = frozenset(
    {
        "prompt",
        "api_key",
        "apikey",
        "authorization",
        "password",
        "senha",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "client_secret",
        "response",
        "text",
        "audio",
        "content",
        "raw",
    }
)

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(api[_-]?key|authorization|bearer|token|password|senha)\s*[:=]\s*\S+"),
    re.compile(r"(?i)sk-[a-z0-9]{10,}"),
    re.compile(r"(?i)xai-[a-z0-9]{10,}"),
)


@dataclass(frozen=True)
class RouterEvent:
    """Evento estruturado de uma decisão/execução do roteador."""

    request_id: str
    timestamp: float
    intent: str
    selected_model: str
    fallback_used: bool
    fallback_model: str | None
    latency_ms: float
    tokens: int | None
    cost: float
    approval_required: bool
    outcome: Outcome
    reason: str = ""
    provider: str = "ollama"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        sanitize_log_payload(payload)
        return payload


@dataclass
class RouterObserver:
    """Coletor em memória (e opcionalmente JSONL) de eventos do roteador."""

    path: Path | None = None
    events: list[RouterEvent] = field(default_factory=list)

    def record(
        self,
        *,
        request_id: str,
        intent: str,
        selected_model: str,
        fallback_used: bool,
        fallback_model: str | None,
        latency_ms: float,
        tokens: int | None,
        cost: float,
        approval_required: bool,
        outcome: Outcome,
        reason: str = "",
        provider: str = "ollama",
        timestamp: float | None = None,
    ) -> RouterEvent:
        event = RouterEvent(
            request_id=request_id,
            timestamp=time.time() if timestamp is None else timestamp,
            intent=intent,
            selected_model=selected_model,
            fallback_used=fallback_used,
            fallback_model=fallback_model,
            latency_ms=latency_ms,
            tokens=tokens,
            cost=cost,
            approval_required=approval_required,
            outcome=outcome,
            reason=redact_secrets(reason),
            provider=provider,
        )
        payload = event.to_dict()
        self.events.append(event)
        if self.path is not None:
            self._append_jsonl(payload)
        return event

    def _append_jsonl(self, payload: Mapping[str, Any]) -> None:
        assert self.path is not None
        sanitize_log_payload(dict(payload))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":"))
        if contains_secret(line):
            raise SafetyViolationError("log recusou linha com possível segredo")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def sanitize_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove campos proibidos e reda valores suspeitos."""

    for key in list(payload.keys()):
        folded = key.casefold()
        if folded in FORBIDDEN_LOG_KEYS or folded.endswith("_secret") or folded.endswith(
            "_password"
        ):
            raise SafetyViolationError(f"campo proibido no log: {key}")
        # "tokens" (contagem) é permitido; "token"/"api_key" não.
        if folded != "tokens" and (
            folded.endswith("_token") or folded in {"api_key", "apikey"}
        ):
            raise SafetyViolationError(f"campo proibido no log: {key}")
        value = payload[key]
        if isinstance(value, str):
            payload[key] = redact_secrets(value)
        elif isinstance(value, dict):
            sanitize_log_payload(value)
    return payload


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def contains_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def estimate_tokens(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, len(stripped) // 4)


def estimate_cost_local(*, tokens: int | None) -> float:
    """Custo local é zero (sem nuvem)."""

    _ = tokens
    return 0.0
