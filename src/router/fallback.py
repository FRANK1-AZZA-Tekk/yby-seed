"""Política de fallback local do roteador (sem nuvem, sem Ollama real)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from src.router.errors import RouterError, SafetyViolationError
from src.router.registry import ModelEntry, ModelRegistry

Invoker = Callable[[ModelEntry, str], str]


class FallbackError(RouterError):
    """Primary e fallback locais falharam; erro seguro sem nuvem."""


@dataclass(frozen=True)
class AttemptRecord:
    model: str
    role: str
    success: bool
    reason: str
    latency_ms: float
    error: str | None = None
    response_text: str | None = None


@dataclass(frozen=True)
class FallbackResult:
    text: str
    selected_model: str
    used_fallback: bool
    fallback_model: str | None
    fallback_reason: str | None
    attempts: tuple[AttemptRecord, ...]
    latency_ms: float


@dataclass
class FallbackPolicy:
    """Tenta o modelo principal e, se falhar, o fallback local."""

    registry: ModelRegistry
    max_retries: int = 1
    overall_timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries deve ser >= 0")
        if self.overall_timeout_seconds <= 0:
            raise ValueError("overall_timeout_seconds deve ser > 0")

    def execute(
        self,
        *,
        primary: ModelEntry,
        prompt: str,
        invoker: Invoker,
        deadline: float | None = None,
    ) -> FallbackResult:
        """Executa primary → fallback local. Nunca usa nuvem."""

        self._assert_local(primary)
        started = time.monotonic()
        hard_deadline = (
            deadline
            if deadline is not None
            else started + self.overall_timeout_seconds
        )
        attempts: list[AttemptRecord] = []

        primary_error: str | None = None
        for attempt_idx in range(self.max_retries + 1):
            self._check_deadline(started, hard_deadline)
            record = self._invoke(
                entry=primary,
                prompt=prompt,
                invoker=invoker,
                hard_deadline=hard_deadline,
                reason=f"primary_attempt_{attempt_idx}",
            )
            attempts.append(record)
            if record.success and record.response_text is not None:
                return FallbackResult(
                    text=record.response_text,
                    selected_model=primary.model,
                    used_fallback=False,
                    fallback_model=None,
                    fallback_reason=None,
                    attempts=tuple(attempts),
                    latency_ms=_elapsed_ms(started),
                )
            primary_error = record.error or "falha no modelo principal"

        fallback = self.registry.fallback_entry()
        self._assert_local(fallback)
        if fallback.model == primary.model:
            raise FallbackError(
                "fallback local idêntico ao principal e o principal falhou; "
                "nuvem não será usada."
            )

        fallback_reason = (
            f"primary_failed:{primary.model}:{primary_error}; "
            f"switching_to_local_fallback:{fallback.model}"
        )
        self._check_deadline(started, hard_deadline)
        fb_record = self._invoke(
            entry=fallback,
            prompt=prompt,
            invoker=invoker,
            hard_deadline=hard_deadline,
            reason=fallback_reason,
        )
        attempts.append(fb_record)
        if fb_record.success and fb_record.response_text is not None:
            return FallbackResult(
                text=fb_record.response_text,
                selected_model=fallback.model,
                used_fallback=True,
                fallback_model=fallback.model,
                fallback_reason=fallback_reason,
                attempts=tuple(attempts),
                latency_ms=_elapsed_ms(started),
            )

        raise FallbackError(
            "fallback local esgotado; nuvem bloqueada. "
            f"primary={primary.model!r} fallback={fallback.model!r} "
            f"erro={fb_record.error!r}"
        )

    def _invoke(
        self,
        *,
        entry: ModelEntry,
        prompt: str,
        invoker: Invoker,
        hard_deadline: float,
        reason: str,
    ) -> AttemptRecord:
        remaining = hard_deadline - time.monotonic()
        if remaining <= 0:
            return AttemptRecord(
                model=entry.model,
                role=entry.role,
                success=False,
                reason=reason,
                latency_ms=0.0,
                error="timeout geral do fallback",
            )
        per_call_timeout = min(entry.timeout, remaining)
        t0 = time.monotonic()
        try:
            text = _call_with_timeout(
                invoker, entry, prompt, timeout=per_call_timeout
            )
            return AttemptRecord(
                model=entry.model,
                role=entry.role,
                success=True,
                reason=reason,
                latency_ms=(time.monotonic() - t0) * 1000.0,
                response_text=text,
            )
        except Exception as exc:  # noqa: BLE001 — falha do invoker injetado
            return AttemptRecord(
                model=entry.model,
                role=entry.role,
                success=False,
                reason=reason,
                latency_ms=(time.monotonic() - t0) * 1000.0,
                error=str(exc),
            )

    @staticmethod
    def _assert_local(entry: ModelEntry) -> None:
        if entry.allow_cloud:
            raise SafetyViolationError(
                f"modelo {entry.model!r} com allow_cloud=true bloqueado no fallback"
            )
        if entry.provider not in {"ollama", "local"}:
            raise SafetyViolationError(
                f"fallback recusou provider não local: {entry.provider!r}"
            )

    @staticmethod
    def _check_deadline(started: float, hard_deadline: float) -> None:
        if time.monotonic() >= hard_deadline:
            raise FallbackError(
                f"timeout do fallback após {_elapsed_ms(started):.1f}ms; "
                "nuvem bloqueada"
            )


def _elapsed_ms(started: float) -> float:
    return (time.monotonic() - started) * 1000.0


def _call_with_timeout(
    invoker: Invoker,
    entry: ModelEntry,
    prompt: str,
    *,
    timeout: float,
) -> str:
    """Timeout cooperativo sobre invoker injetado (sem threads / sem Ollama)."""

    if timeout <= 0:
        raise TimeoutError("timeout <= 0")
    t0 = time.monotonic()
    bounded = ModelEntry(
        role=entry.role,
        provider=entry.provider,
        model=entry.model,
        context=entry.context,
        max_tokens=entry.max_tokens,
        timeout=timeout,
        enabled=entry.enabled,
        allow_cloud=False,
        allowed_tools=entry.allowed_tools,
        is_agent_primary=entry.is_agent_primary,
    )
    result = invoker(bounded, prompt)
    elapsed = time.monotonic() - t0
    if elapsed > timeout:
        raise TimeoutError(
            f"invocação excedeu timeout de {timeout:.3f}s ({elapsed:.3f}s)"
        )
    if not isinstance(result, str) or not result.strip():
        raise ValueError("resposta vazia do modelo local")
    return result
