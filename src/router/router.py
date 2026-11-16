"""Fachada do roteador offline: classify → modelo → fallback → agente."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from src.agent_loop.planner import Planner, ScriptedPlanner
from src.agent_loop.tools import ToolRegistry, default_tool_registry
from src.memory.vault import Vault
from src.router.classifier import classify
from src.router.errors import RoutingError, SafetyViolationError
from src.router.fallback import FallbackError, FallbackPolicy, FallbackResult, Invoker
from src.router.integration import AgentBridge, AgentBridgeResult, ApprovalFn
from src.router.observability import (
    RouterObserver,
    estimate_cost_local,
    estimate_tokens,
)
from src.router.registry import ModelRegistry
from src.router.schemas import Request, RouteDecision


@dataclass(frozen=True)
class RouterResponse:
    """Resposta estruturada ponta a ponta do roteador + agente."""

    request_id: str
    decision: RouteDecision
    status: str
    answer: dict[str, Any] | None
    sources: list[dict[str, Any]]
    tools_used: list[str]
    selected_model: str
    fallback_used: bool
    fallback_model: str | None
    fallback_reason: str | None
    latency_ms: float
    approval_required: bool
    approved: bool
    blocked_reason: str | None = None
    agent_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "intent": self.decision.intent,
            "risk": self.decision.risk,
            "selected_model": self.selected_model,
            "fallback_used": self.fallback_used,
            "fallback_model": self.fallback_model,
            "fallback_reason": self.fallback_reason,
            "tools_used": list(self.tools_used),
            "sources": list(self.sources),
            "answer": self.answer,
            "latency_ms": self.latency_ms,
            "approval_required": self.approval_required,
            "approved": self.approved,
            "blocked_reason": self.blocked_reason,
            "agent_status": self.agent_status,
            "allow_cloud": self.decision.constraints.allow_cloud,
        }


@dataclass
class OfflineRouter:
    """Orquestra classificador, registry, fallback e agent_loop sem nuvem."""

    model_registry: ModelRegistry = field(default_factory=ModelRegistry.default)
    observer: RouterObserver = field(default_factory=RouterObserver)
    tool_registry: ToolRegistry | None = None
    vault: Vault | None = None
    approval_fn: ApprovalFn | None = None
    invoker: Invoker | None = None
    planner_factory: Callable[[RouteDecision], Planner] | None = None
    max_fallback_retries: int = 0

    def handle(
        self,
        text: str | Request | Mapping[str, object],
        *,
        approved: bool | None = None,
        planner: Planner | None = None,
    ) -> RouterResponse:
        started = time.monotonic()
        request = _as_request(text)
        decision = classify(request)
        if decision.constraints.allow_cloud:
            raise SafetyViolationError("nuvem bloqueada no Offline router")

        primary = self.model_registry.primary_for_intent(decision.intent)
        # Alinha selected_model da decisão ao registry (fonte de verdade operacional).
        if primary.model != decision.selected_model:
            # Mantém decisão do classificador como política; registry confirma disponibilidade.
            try:
                self.model_registry.get_by_model(decision.selected_model)
            except Exception as exc:  # ModelNotFoundError
                raise RoutingError(
                    f"modelo da decisão ausente no registry: {decision.selected_model}"
                ) from exc

        fallback_used = False
        fallback_model: str | None = None
        fallback_reason: str | None = None
        model_text: str | None = None

        if self.invoker is not None:
            policy = FallbackPolicy(
                registry=self.model_registry,
                max_retries=self.max_fallback_retries,
                overall_timeout_seconds=min(
                    decision.constraints.timeout_seconds, primary.timeout + 30.0
                ),
            )
            try:
                fb: FallbackResult = policy.execute(
                    primary=primary,
                    prompt=request.text,
                    invoker=self.invoker,
                )
            except FallbackError as exc:
                latency = (time.monotonic() - started) * 1000.0
                self.observer.record(
                    request_id=request.request_id,
                    intent=decision.intent,
                    selected_model=decision.selected_model,
                    fallback_used=True,
                    fallback_model=self.model_registry.fallback_entry().model,
                    latency_ms=latency,
                    tokens=estimate_tokens(request.text),
                    cost=0.0,
                    approval_required=decision.requires_approval,
                    outcome="error",
                    reason=f"fallback_exhausted:{exc}",
                )
                return RouterResponse(
                    request_id=request.request_id,
                    decision=decision,
                    status="error",
                    answer=None,
                    sources=[],
                    tools_used=[],
                    selected_model=decision.selected_model,
                    fallback_used=True,
                    fallback_model=self.model_registry.fallback_entry().model,
                    fallback_reason=str(exc),
                    latency_ms=latency,
                    approval_required=decision.requires_approval,
                    approved=False,
                    blocked_reason=None,
                    agent_status=None,
                )
            model_text = fb.text
            fallback_used = fb.used_fallback
            fallback_model = fb.fallback_model
            fallback_reason = fb.fallback_reason
            selected_model = fb.selected_model
        else:
            selected_model = decision.selected_model

        bridge = AgentBridge(
            tool_registry=self.tool_registry
            or default_tool_registry(vault=self.vault, include_vault=self.vault is not None),
            planner=planner
            or self._default_planner(decision, model_text=model_text),
            approval_fn=self.approval_fn,
            vault=self.vault,
        )
        bridge_result = bridge.run(
            user_text=request.text,
            decision=decision,
            approved=approved,
        )
        latency = (time.monotonic() - started) * 1000.0
        return self._finalize(
            request_id=request.request_id,
            decision=decision,
            bridge_result=bridge_result,
            selected_model=selected_model,
            fallback_used=fallback_used,
            fallback_model=fallback_model,
            fallback_reason=fallback_reason,
            latency_ms=latency,
            prompt_for_tokens=request.text,
        )

    def _default_planner(
        self, decision: RouteDecision, *, model_text: str | None
    ) -> Planner:
        if self.planner_factory is not None:
            return self.planner_factory(decision)
        answer: dict[str, Any] = {
            "summary": "resposta local via roteador",
            "intent": decision.intent,
            "model": decision.selected_model,
        }
        if model_text:
            answer["model_output"] = model_text[:500]
        return ScriptedPlanner(
            [
                {
                    "action": "finish",
                    "answer": answer,
                }
            ]
        )

    def _finalize(
        self,
        *,
        request_id: str,
        decision: RouteDecision,
        bridge_result: AgentBridgeResult,
        selected_model: str,
        fallback_used: bool,
        fallback_model: str | None,
        fallback_reason: str | None,
        latency_ms: float,
        prompt_for_tokens: str,
    ) -> RouterResponse:
        sources = bridge_result.rag.sources() if bridge_result.rag else []
        if not bridge_result.approved:
            self.observer.record(
                request_id=request_id,
                intent=decision.intent,
                selected_model=selected_model,
                fallback_used=fallback_used,
                fallback_model=fallback_model,
                latency_ms=latency_ms,
                tokens=estimate_tokens(prompt_for_tokens),
                cost=estimate_cost_local(tokens=estimate_tokens(prompt_for_tokens)),
                approval_required=True,
                outcome="blocked",
                reason=bridge_result.blocked_reason or "approval_required",
            )
            return RouterResponse(
                request_id=request_id,
                decision=decision,
                status="blocked",
                answer=None,
                sources=sources,
                tools_used=[],
                selected_model=selected_model,
                fallback_used=fallback_used,
                fallback_model=fallback_model,
                fallback_reason=fallback_reason,
                latency_ms=latency_ms,
                approval_required=True,
                approved=False,
                blocked_reason=bridge_result.blocked_reason,
            )

        assert bridge_result.agent is not None
        agent = bridge_result.agent
        outcome = "fallback_success" if fallback_used else "success"
        if agent.status != "completed":
            outcome = "error"
        tokens = estimate_tokens(prompt_for_tokens)
        self.observer.record(
            request_id=request_id,
            intent=decision.intent,
            selected_model=selected_model,
            fallback_used=fallback_used,
            fallback_model=fallback_model,
            latency_ms=latency_ms,
            tokens=tokens,
            cost=estimate_cost_local(tokens=tokens),
            approval_required=decision.requires_approval,
            outcome=outcome,  # type: ignore[arg-type]
            reason=(
                f"agent_status={agent.status}; tools={','.join(bridge_result.tools_used) or 'none'}"
                + (f"; fallback={fallback_reason}" if fallback_reason else "")
            ),
        )
        return RouterResponse(
            request_id=request_id,
            decision=decision,
            status="ok" if agent.status == "completed" else agent.status,
            answer=agent.final_answer,
            sources=sources,
            tools_used=list(bridge_result.tools_used),
            selected_model=selected_model,
            fallback_used=fallback_used,
            fallback_model=fallback_model,
            fallback_reason=fallback_reason,
            latency_ms=latency_ms,
            approval_required=decision.requires_approval,
            approved=True,
            agent_status=agent.status,
        )


def _as_request(value: str | Request | Mapping[str, object]) -> Request:
    if isinstance(value, Request):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise RoutingError("entrada inválida: texto vazio.")
        return Request(
            request_id=f"req-{uuid.uuid4().hex[:12]}",
            text=text,
        )
    return Request.model_validate(value)
