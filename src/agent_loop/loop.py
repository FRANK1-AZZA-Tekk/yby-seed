"""Loop de agente com teto de iterações e abort explícito."""

from __future__ import annotations

import json
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ValidationError

from src.agent_loop.planner import Planner
from src.engine.providers import ProviderError
from src.agent_loop.schemas import AbortStep, FinishStep, ToolCallStep, format_validation_error
from src.agent_loop.tools import ToolRegistry

AgentStatus = Literal["completed", "aborted", "max_steps", "error"]


@dataclass
class StepRecord:
    iteration: int
    kind: str
    detail: dict[str, Any]
    error: str | None = None


@dataclass
class AgentRunResult:
    status: AgentStatus
    task: str
    steps: list[StepRecord] = field(default_factory=list)
    final_answer: dict[str, Any] | None = None
    abort_reason: str | None = None

    @property
    def iterations(self) -> int:
        return len(self.steps)


class ControlledAgentLoop:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        planner: Planner,
        max_iterations: int = 8,
        tool_timeout_seconds: float | None = 30.0,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations deve ser >= 1")
        if tool_timeout_seconds is not None and tool_timeout_seconds <= 0:
            raise ValueError("tool_timeout_seconds deve ser positivo ou None")
        self.registry = registry
        self.planner = planner
        self.max_iterations = max_iterations
        self.tool_timeout_seconds = tool_timeout_seconds

    def run(self, task: str) -> AgentRunResult:
        task = task.strip()
        if not task:
            return AgentRunResult(
                status="error",
                task="",
                steps=[StepRecord(0, "error", {}, "tarefa vazia")],
            )

        history: list[dict[str, object]] = []
        tools_blurb = self.registry.describe_for_prompt()

        for i in range(1, self.max_iterations + 1):
            try:
                step = self.planner.plan(
                    task=task,
                    tools_blurb=tools_blurb,
                    history=history,
                )
            except (ValueError, ValidationError, json.JSONDecodeError, ProviderError) as exc:
                err = (
                    format_validation_error(exc)
                    if isinstance(exc, ValidationError)
                    else str(exc)
                )
                return AgentRunResult(
                    status="error",
                    task=task,
                    steps=_history_to_records(history)
                    + [StepRecord(i, "planner_error", {}, err)],
                )

            if isinstance(step, AbortStep):
                history.append({"action": "abort", "reason": step.reason})
                return AgentRunResult(
                    status="aborted",
                    task=task,
                    steps=_history_to_records(history),
                    abort_reason=step.reason,
                )

            if isinstance(step, FinishStep):
                history.append({"action": "finish", "answer": step.answer})
                return AgentRunResult(
                    status="completed",
                    task=task,
                    steps=_history_to_records(history),
                    final_answer=step.answer,
                )

            if isinstance(step, ToolCallStep):
                record: dict[str, object] = {
                    "action": "tool",
                    "name": step.name,
                    "arguments": step.arguments,
                }
                try:
                    result = self._run_tool(step.name, step.arguments)
                    record["result"] = result
                except Exception as exc:
                    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                        raise
                    record["error"] = str(exc)
                    history.append(record)
                    return AgentRunResult(
                        status="error",
                        task=task,
                        steps=_history_to_records(history),
                    )
                history.append(record)
                continue

        return AgentRunResult(
            status="max_steps",
            task=task,
            steps=_history_to_records(history),
            abort_reason=f"limite de {self.max_iterations} iterações",
        )

    def _run_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.tool_timeout_seconds is None:
            return self.registry.run(name, arguments)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.registry.run, name, arguments)
            try:
                return future.result(timeout=self.tool_timeout_seconds)
            except FuturesTimeoutError as exc:
                raise TimeoutError(
                    f"tool {name!r} excedeu {self.tool_timeout_seconds:.0f}s"
                ) from exc


def _history_to_records(history: Sequence[dict[str, object]]) -> list[StepRecord]:
    records: list[StepRecord] = []
    for idx, item in enumerate(history, start=1):
        action = str(item.get("action", "?"))
        err = item.get("error")
        records.append(
            StepRecord(
                iteration=idx,
                kind=action,
                detail={k: v for k, v in item.items() if k != "error"},
                error=str(err) if err is not None else None,
            )
        )
    return records