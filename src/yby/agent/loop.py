"""Loop controlado do agente YBY (RAG + 3 ferramentas)."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import ValidationError

from src.engine.providers import ProviderError
from src.yby.agent.runner import create_default_planner
from src.yby.agent.safety import validate_user_question, warnings_from_rag_chunk
from src.yby.agent.schemas import (
    AgentAbortStep,
    AgentFinishAnswer,
    AgentFinishStep,
    AgentStep,
    AgentStructuredResponse,
    AgentToolStep,
    format_validation_error,
    parse_agent_step,
)
from src.yby.tools.registry import ToolRegistry, create_default_registry

logger = logging.getLogger("yby.agent")

MAX_ITERATIONS = 5
MAX_TOOL_CALLS = 3
DEFAULT_AGENT_LOG = Path("logs/agent_runs.jsonl")


class AgentPlanner(Protocol):
    def plan(
        self,
        *,
        question: str,
        tools_blurb: str,
        history: Sequence[dict[str, Any]],
        tools_remaining: int,
        safety_warnings: list[str] | None = None,
    ) -> AgentStep: ...


@dataclass
class YbyAgentResult:
    status: Literal["completed", "aborted", "max_steps", "max_tools", "error"]
    question: str
    trace_id: str
    answer: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    structured_action: dict[str, Any] | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    telemetry: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    structured: AgentStructuredResponse | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "status": self.status,
            "question": self.question,
            "trace_id": self.trace_id,
            "answer": self.answer,
            "sources": self.sources,
            "tools_used": self.tools_used,
            "structured_action": self.structured_action,
            "steps": self.steps,
            "telemetry": self.telemetry,
            "warnings": self.warnings,
        }
        if self.structured is not None:
            payload["structured"] = self.structured.model_dump()
        return payload


class ScriptedYbyPlanner:
    """Sequência fixa de passos para testes."""

    def __init__(self, steps: Sequence[str | dict[str, Any]]) -> None:
        parsed: list[AgentStep] = []
        for item in steps:
            raw = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
            parsed.append(parse_agent_step(raw))
        self._steps = parsed
        self._index = 0

    def plan(
        self,
        *,
        question: str,
        tools_blurb: str,
        history: Sequence[dict[str, Any]],
        tools_remaining: int,
        safety_warnings: list[str] | None = None,
    ) -> AgentStep:
        _ = (question, tools_blurb, history, tools_remaining, safety_warnings)
        if self._index >= len(self._steps):
            return parse_agent_step('{"action":"abort","reason":"script esgotado"}')
        step = self._steps[self._index]
        self._index += 1
        return step


class FailingPlanner:
    """Falha Ollama para testes."""

    def plan(
        self,
        *,
        question: str,
        tools_blurb: str,
        history: Sequence[dict[str, Any]],
        tools_remaining: int,
        safety_warnings: list[str] | None = None,
    ) -> AgentStep:
        _ = (question, tools_blurb, history, tools_remaining, safety_warnings)
        raise ProviderError("Ollama indisponível (simulado)")


class YbyAgentLoop:
    def __init__(
        self,
        *,
        registry: ToolRegistry | None = None,
        planner: AgentPlanner | None = None,
        max_iterations: int = MAX_ITERATIONS,
        max_tool_calls: int = MAX_TOOL_CALLS,
        log_path: Path | None = None,
    ) -> None:
        self.registry = registry or create_default_registry()
        self.planner = planner or create_default_planner()
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls
        self.log_path = log_path or Path(os.getenv("YBY_AGENT_LOG_PATH", str(DEFAULT_AGENT_LOG)))
        self._ollama_metrics: list[dict[str, Any]] = []

    def run(self, question: str) -> YbyAgentResult:
        trace_id = uuid.uuid4().hex
        started = time.perf_counter()
        validation = validate_user_question(question)
        if not validation.ok:
            return self._finalize_error(
                trace_id=trace_id,
                started=started,
                question=validation.question,
                message=validation.error_message or "entrada inválida",
                code=validation.error_code or "invalid_question",
                tools_used=[],
            )

        q = validation.question
        run_warnings = list(validation.warnings)
        history: list[dict[str, Any]] = []
        tools_blurb = _tools_blurb(self.registry)
        tools_used: list[str] = []
        rag_sources: list[dict[str, Any]] = []
        tool_calls = 0
        structured_action: dict[str, Any] | None = None

        for _iteration in range(1, self.max_iterations + 1):
            tools_remaining = max(0, self.max_tool_calls - tool_calls)
            try:
                step = self.planner.plan(
                    question=q,
                    tools_blurb=tools_blurb,
                    history=history,
                    tools_remaining=tools_remaining,
                    safety_warnings=run_warnings,
                )
                _record_ollama_metrics(self.planner, self._ollama_metrics)
            except (ValueError, ValidationError, json.JSONDecodeError, ProviderError) as exc:
                err = format_validation_error(exc) if isinstance(exc, ValidationError) else str(exc)
                history.append({"action": "planner_error", "error": err})
                return self._finalize_error(
                    trace_id=trace_id,
                    started=started,
                    question=q,
                    message=err,
                    code="planner_error" if isinstance(exc, ProviderError) else "parse_error",
                    tools_used=tools_used,
                    steps=history,
                    warnings=run_warnings,
                )

            if isinstance(step, AgentAbortStep):
                history.append({"action": "abort", "reason": step.reason})
                return self._build_result(
                    trace_id=trace_id,
                    started=started,
                    status="aborted",
                    question=q,
                    history=history,
                    tools_used=tools_used,
                    rag_sources=rag_sources,
                    warnings=run_warnings,
                    structured_action=structured_action,
                )

            if isinstance(step, AgentFinishStep):
                answer_model = _coerce_finish_answer(step.answer)
                sources = [_source_dict(s) for s in answer_model.sources]
                if not sources and rag_sources:
                    sources = rag_sources
                answer = answer_model.model_dump()
                answer["sources"] = sources
                run_warnings.extend(answer_model.warnings)
                history.append({"action": "finish", "answer": answer})
                return self._build_result(
                    trace_id=trace_id,
                    started=started,
                    status="completed",
                    question=q,
                    history=history,
                    tools_used=tools_used,
                    rag_sources=sources,
                    warnings=run_warnings,
                    structured_action=structured_action,
                    answer=answer,
                )

            if isinstance(step, AgentToolStep):
                structured_action = {
                    "action": "tool",
                    "name": step.name,
                    "arguments": step.arguments,
                    "justification": step.justification,
                }
                if tool_calls >= self.max_tool_calls:
                    history.append(
                        {
                            "action": "tool_blocked",
                            "name": step.name,
                            "error": "limite de ferramentas atingido",
                        }
                    )
                    return self._build_result(
                        trace_id=trace_id,
                        started=started,
                        status="max_tools",
                        question=q,
                        history=history,
                        tools_used=tools_used,
                        rag_sources=rag_sources,
                        warnings=run_warnings,
                        structured_action=structured_action,
                    )

                if step.name not in self.registry.names():
                    history.append(
                        {
                            "action": "tool",
                            "name": step.name,
                            "error": "ferramenta não allowlisted",
                        }
                    )
                    return self._finalize_error(
                        trace_id=trace_id,
                        started=started,
                        question=q,
                        message="ferramenta não registrada",
                        code="tool_not_allowed",
                        tools_used=tools_used,
                        steps=history,
                        warnings=run_warnings,
                        structured_action=structured_action,
                    )

                tool_response = self.registry.run(step.name, step.arguments)
                history.append(
                    {
                        "action": "tool",
                        "name": step.name,
                        "arguments": step.arguments,
                        "justification": step.justification,
                        "result": tool_response.to_dict(),
                    }
                )
                tool_calls += 1
                tools_used.append(step.name)

                if step.name == "search_knowledge" and tool_response.ok and tool_response.data:
                    rag_sources.extend(_sources_from_search(tool_response.data))
                    for hit in tool_response.data.get("hits") or []:
                        if isinstance(hit, dict):
                            run_warnings.extend(warnings_from_rag_chunk(str(hit.get("text", ""))))

                if tool_response.requires_approval:
                    return self._finalize_error(
                        trace_id=trace_id,
                        started=started,
                        question=q,
                        message="aprovação humana necessária",
                        code="approval_required",
                        tools_used=tools_used,
                        steps=history,
                        warnings=run_warnings,
                        structured_action=structured_action,
                    )

        return self._build_result(
            trace_id=trace_id,
            started=started,
            status="max_steps",
            question=q,
            history=history,
            tools_used=tools_used,
            rag_sources=rag_sources,
            warnings=run_warnings,
            structured_action=structured_action,
        )

    def _finalize_error(
        self,
        *,
        trace_id: str,
        started: float,
        question: str,
        message: str,
        code: str,
        tools_used: list[str],
        steps: list[dict[str, Any]] | None = None,
        warnings: list[str] | None = None,
        structured_action: dict[str, Any] | None = None,
    ) -> YbyAgentResult:
        return self._build_result(
            trace_id=trace_id,
            started=started,
            status="error",
            question=question,
            history=steps or [{"action": "error", "code": code, "message": message}],
            tools_used=tools_used,
            rag_sources=[],
            warnings=warnings or [],
            structured_action=structured_action,
            error_message=message,
        )

    def _build_result(
        self,
        *,
        trace_id: str,
        started: float,
        status: str,
        question: str,
        history: list[dict[str, Any]],
        tools_used: list[str],
        rag_sources: list[dict[str, Any]],
        warnings: list[str],
        structured_action: dict[str, Any] | None = None,
        answer: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> YbyAgentResult:
        latency_ms = (time.perf_counter() - started) * 1000
        telemetry = _build_telemetry(latency_ms, tools_used, self._ollama_metrics, status)

        answer_text = ""
        confidence: Literal["low", "medium", "high"] = "low"
        needs_approval = False
        sources = rag_sources
        if answer:
            answer_text = str(answer.get("text", ""))
            confidence = answer.get("confidence", "medium")  # type: ignore[assignment]
            needs_approval = bool(answer.get("needs_approval", False))
            sources = answer.get("sources") or rag_sources
        elif error_message:
            answer_text = error_message

        structured = AgentStructuredResponse(
            answer=answer_text,
            sources=sources,
            tools_used=list(tools_used),
            confidence=confidence,
            needs_approval=needs_approval,
            warnings=list(dict.fromkeys(warnings)),
            trace_id=trace_id,
            latency_ms=round(latency_ms, 2),
            token_usage=_token_usage(self._ollama_metrics),
            status=status,
        )

        result = YbyAgentResult(
            status=status,  # type: ignore[arg-type]
            question=question,
            trace_id=trace_id,
            answer=answer,
            sources=sources,
            tools_used=tools_used,
            structured_action=structured_action,
            steps=history,
            telemetry=telemetry,
            warnings=structured.warnings,
            structured=structured,
        )
        _write_run_log(self.log_path, result)
        return result


def _coerce_finish_answer(raw: AgentFinishAnswer | dict[str, Any]) -> AgentFinishAnswer:
    if isinstance(raw, AgentFinishAnswer):
        return raw
    return AgentFinishAnswer.model_validate(raw)


def _source_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if isinstance(item, dict):
        return item
    return {}


def _tools_blurb(registry: ToolRegistry) -> str:
    lines = []
    for item in registry.describe_all():
        lines.append(f"- {item['name']}: {item['description']}")
    return "\n".join(lines)


def _sources_from_search(data: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for hit in data.get("hits") or []:
        if not isinstance(hit, dict):
            continue
        sources.append(
            {
                "source": hit.get("source", ""),
                "excerpt": hit.get("text", ""),
                "score": hit.get("score"),
                "title": hit.get("title", ""),
                "doc_type": hit.get("doc_type", ""),
            }
        )
    return sources


def _record_ollama_metrics(planner: AgentPlanner, bucket: list[dict[str, Any]]) -> None:
    provider = getattr(planner, "_provider", None)
    metrics = getattr(provider, "last_metrics", None)
    if metrics is None:
        return
    bucket.append(
        {
            "duration_ms": round(metrics.duration_ms, 2),
            "prompt_eval_count": metrics.prompt_eval_count,
            "eval_count": metrics.eval_count,
            "model": metrics.model,
            "estimated_cost_usd": 0.0,
        }
    )


def _token_usage(ollama_calls: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not ollama_calls:
        return None
    prompt = sum(call.get("prompt_eval_count") or 0 for call in ollama_calls)
    completion = sum(call.get("eval_count") or 0 for call in ollama_calls)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "estimated_cost_usd": 0.0,
    }


def _build_telemetry(
    latency_ms: float,
    tools_used: list[str],
    ollama_calls: list[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    return {
        "latency_ms": round(latency_ms, 2),
        "tools_used": tools_used,
        "ollama_calls": ollama_calls,
        "total_tokens_estimate": (_token_usage(ollama_calls) or {}).get("total_tokens", 0),
        "estimated_cost_usd": 0.0,
        "provider": "ollama_local",
        "status": status,
    }


def _write_run_log(path: Path, result: YbyAgentResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "event": "agent_run",
            "trace_id": result.trace_id,
            "status": result.status,
            "question_length": len(result.question),
            "tools_used": result.tools_used,
            "telemetry": result.telemetry,
            "sources_count": len(result.sources),
            "warnings_count": len(result.warnings),
        },
        ensure_ascii=False,
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    logger.info(line)