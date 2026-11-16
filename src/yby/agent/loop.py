"""Loop mínimo: Ollama local, ferramentas YBY e citações de RAG."""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import requests
from pydantic import ValidationError

from src.engine.config import EngineConfig
from src.engine.providers import OllamaProvider, ProviderError, build_ollama_generate_payload
from src.yby.agent.schemas import (
    AgentAbortStep,
    AgentFinishStep,
    AgentStep,
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
    ) -> AgentStep: ...


@dataclass(frozen=True)
class OllamaTurnMetrics:
    duration_ms: float
    prompt_eval_count: int | None
    eval_count: int | None
    model: str


class YbyPlanner:
    """Planejador via Ollama (`/api/generate`)."""

    SYSTEM = (
        "Você é o agente YBY SEED (local-first, português do Brasil). "
        "Responda APENAS com um único objeto JSON, sem texto extra.\n"
        "Para perguntas sobre o projeto, documentação ou decisões, prefira "
        'search_knowledge antes de concluir.\n'
        'Chamar ferramenta: {"action":"tool","name":"...","arguments":{...},'
        '"justification":"por que esta tool"}\n'
        'Concluir: {"action":"finish","answer":{"text":"...","sources":'
        '[{"source":"caminho","excerpt":"trecho","score":0.0}]}}\n'
        'Abortar: {"action":"abort","reason":"..."}\n'
        "Use somente tools listadas. Não invente APIs, escrita em disco, rede ou código."
    )

    def __init__(
        self,
        provider: OllamaProvider,
        *,
        model: str,
    ) -> None:
        self._provider = provider
        self._model = model

    def plan(
        self,
        *,
        question: str,
        tools_blurb: str,
        history: Sequence[dict[str, Any]],
        tools_remaining: int,
    ) -> AgentStep:
        limit_note = (
            f"Ferramentas restantes nesta tarefa: {tools_remaining}. "
            "Se for 0, responda com finish ou abort sem chamar tool."
        )
        history_text = json.dumps(list(history), ensure_ascii=False)
        prompt = (
            f"Pergunta do usuário: {question}\n\n"
            f"Tools disponíveis:\n{tools_blurb}\n\n"
            f"{limit_note}\n\n"
            f"Histórico (JSON):\n{history_text}\n\n"
            "Próximo passo (um JSON):"
        )
        raw = self._provider.complete(prompt, model=self._model, system=self.SYSTEM)
        return parse_agent_step(raw)


class InstrumentedOllamaProvider(OllamaProvider):
    """Ollama com métricas por chamada para telemetria."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.last_metrics: OllamaTurnMetrics | None = None

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        url = f"{self.base_url}/api/generate"
        started = time.perf_counter()
        try:
            response = self._session.post(
                url,
                json=build_ollama_generate_payload(prompt, model=model, system=system),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"Ollama indisponível ({exc})") from exc

        if response.status_code >= 400:
            raise ProviderError(f"Ollama HTTP {response.status_code}")

        payload = response.json()
        text = payload.get("response")
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("resposta vazia do Ollama")

        duration_ms = (time.perf_counter() - started) * 1000
        self.last_metrics = OllamaTurnMetrics(
            duration_ms=duration_ms,
            prompt_eval_count=_as_int(payload.get("prompt_eval_count")),
            eval_count=_as_int(payload.get("eval_count")),
            model=model,
        )
        return text


@dataclass
class YbyAgentResult:
    status: Literal["completed", "aborted", "max_steps", "max_tools", "error"]
    question: str
    answer: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    structured_action: dict[str, Any] | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    telemetry: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "question": self.question,
            "answer": self.answer,
            "sources": self.sources,
            "tools_used": self.tools_used,
            "structured_action": self.structured_action,
            "steps": self.steps,
            "telemetry": self.telemetry,
        }


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
    ) -> AgentStep:
        if self._index >= len(self._steps):
            return parse_agent_step('{"action":"abort","reason":"script esgotado"}')
        step = self._steps[self._index]
        self._index += 1
        return step


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
        self.planner = planner or _default_planner()
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls
        self.log_path = log_path or Path(os.getenv("YBY_AGENT_LOG_PATH", str(DEFAULT_AGENT_LOG)))

        self._ollama_metrics: list[dict[str, Any]] = []

    def run(self, question: str) -> YbyAgentResult:
        started = time.perf_counter()
        question = question.strip()
        if not question:
            return YbyAgentResult(status="error", question="", telemetry=_base_telemetry(0, [], []))

        history: list[dict[str, Any]] = []
        tools_blurb = _tools_blurb(self.registry)
        tools_used: list[str] = []
        rag_sources: list[dict[str, Any]] = []
        tool_calls = 0
        structured_action: dict[str, Any] | None = None

        for iteration in range(1, self.max_iterations + 1):
            tools_remaining = max(0, self.max_tool_calls - tool_calls)
            try:
                step = self.planner.plan(
                    question=question,
                    tools_blurb=tools_blurb,
                    history=history,
                    tools_remaining=tools_remaining,
                )
                _record_ollama_metrics(self.planner, self._ollama_metrics)
            except (ValueError, ValidationError, json.JSONDecodeError, ProviderError) as exc:
                err = format_validation_error(exc) if isinstance(exc, ValidationError) else str(exc)
                history.append({"action": "planner_error", "error": err})
                telemetry = _build_telemetry(
                    started,
                    tools_used,
                    self._ollama_metrics,
                    status="error",
                )
                result = YbyAgentResult(
                    status="error",
                    question=question,
                    steps=history,
                    tools_used=tools_used,
                    structured_action=structured_action,
                    telemetry=telemetry,
                )
                _write_run_log(self.log_path, result)
                return result

            if isinstance(step, AgentAbortStep):
                history.append({"action": "abort", "reason": step.reason})
                telemetry = _build_telemetry(started, tools_used, self._ollama_metrics, "aborted")
                result = YbyAgentResult(
                    status="aborted",
                    question=question,
                    steps=history,
                    tools_used=tools_used,
                    telemetry=telemetry,
                )
                _write_run_log(self.log_path, result)
                return result

            if isinstance(step, AgentFinishStep):
                answer = dict(step.answer)
                sources = _normalize_sources(answer.get("sources"))
                if not sources and rag_sources:
                    sources = rag_sources
                answer["sources"] = sources
                history.append({"action": "finish", "answer": answer})
                telemetry = _build_telemetry(started, tools_used, self._ollama_metrics, "completed")
                result = YbyAgentResult(
                    status="completed",
                    question=question,
                    answer=answer,
                    sources=sources,
                    steps=history,
                    tools_used=tools_used,
                    structured_action=structured_action,
                    telemetry=telemetry,
                )
                _write_run_log(self.log_path, result)
                return result

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
                    telemetry = _build_telemetry(started, tools_used, self._ollama_metrics, "max_tools")
                    result = YbyAgentResult(
                        status="max_tools",
                        question=question,
                        steps=history,
                        tools_used=tools_used,
                        structured_action=structured_action,
                        telemetry=telemetry,
                    )
                    _write_run_log(self.log_path, result)
                    return result

                if step.name not in self.registry.names():
                    history.append(
                        {
                            "action": "tool",
                            "name": step.name,
                            "error": "ferramenta não allowlisted",
                        }
                    )
                    telemetry = _build_telemetry(started, tools_used, self._ollama_metrics, "error")
                    result = YbyAgentResult(
                        status="error",
                        question=question,
                        steps=history,
                        tools_used=tools_used,
                        structured_action=structured_action,
                        telemetry=telemetry,
                    )
                    _write_run_log(self.log_path, result)
                    return result

                tool_response = self.registry.run(step.name, step.arguments)
                record: dict[str, Any] = {
                    "action": "tool",
                    "name": step.name,
                    "arguments": step.arguments,
                    "justification": step.justification,
                    "result": tool_response.to_dict(),
                }
                history.append(record)
                tool_calls += 1
                tools_used.append(step.name)

                if step.name == "search_knowledge" and tool_response.ok and tool_response.data:
                    rag_sources.extend(_sources_from_search(tool_response.data))

                if tool_response.requires_approval:
                    telemetry = _build_telemetry(started, tools_used, self._ollama_metrics, "error")
                    result = YbyAgentResult(
                        status="error",
                        question=question,
                        steps=history,
                        tools_used=tools_used,
                        structured_action=structured_action,
                        telemetry=telemetry,
                    )
                    _write_run_log(self.log_path, result)
                    return result

        telemetry = _build_telemetry(started, tools_used, self._ollama_metrics, "max_steps")
        result = YbyAgentResult(
            status="max_steps",
            question=question,
            steps=history,
            tools_used=tools_used,
            sources=rag_sources,
            structured_action=structured_action,
            telemetry=telemetry,
        )
        _write_run_log(self.log_path, result)
        return result


def _default_planner() -> YbyPlanner:
    config = EngineConfig.from_env()
    provider = InstrumentedOllamaProvider(
        config.ollama_base_url,
        timeout=config.ollama_timeout,
    )
    return YbyPlanner(provider, model=config.local_model)


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
                "metadata": hit.get("metadata", {}),
            }
        )
    return sources


def _normalize_sources(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            out.append(item)
    return out


def _as_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    return None


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


def _base_telemetry(latency_ms: float, tools: list[str], ollama: list[dict]) -> dict[str, Any]:
    return {
        "latency_ms": round(latency_ms, 2),
        "tools_used": tools,
        "ollama_calls": ollama,
        "total_tokens_estimate": sum(
            (call.get("eval_count") or 0) + (call.get("prompt_eval_count") or 0) for call in ollama
        ),
        "estimated_cost_usd": 0.0,
        "provider": "ollama_local",
    }


def _build_telemetry(
    started: float,
    tools_used: list[str],
    ollama_calls: list[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    latency_ms = (time.perf_counter() - started) * 1000
    payload = _base_telemetry(latency_ms, tools_used, ollama_calls)
    payload["status"] = status
    return payload


def _write_run_log(path: Path, result: YbyAgentResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "event": "agent_run",
            "status": result.status,
            "question": result.question,
            "tools_used": result.tools_used,
            "telemetry": result.telemetry,
            "sources_count": len(result.sources),
        },
        ensure_ascii=False,
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    logger.info(line)