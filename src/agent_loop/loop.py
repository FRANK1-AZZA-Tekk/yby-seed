"""Loop de agente com teto de iterações e abort explícito."""

from __future__ import annotations

import json
from collections.abc import Sequence
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
    tools_used: list[str] = field(default_factory=list)

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
        max_tool_calls: int | None = None,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations deve ser >= 1")
        if max_tool_calls is not None and max_tool_calls < 0:
            raise ValueError("max_tool_calls deve ser >= 0")
        self.registry = registry
        self.planner = planner
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls

    def run(self, task: str) -> AgentRunResult:
        task = task.strip()
        if not task:
            return AgentRunResult(
                status="error",
                task="",
                steps=[StepRecord(0, "error", {}, "tarefa vazia")],
            )

        history: list[dict[str, object]] = []
        tools_used: list[str] = []
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
                    tools_used=list(tools_used),
                )

            if isinstance(step, AbortStep):
                history.append({"action": "abort", "reason": step.reason})
                return AgentRunResult(
                    status="aborted",
                    task=task,
                    steps=_history_to_records(history),
                    abort_reason=step.reason,
                    tools_used=list(tools_used),
                )

            if isinstance(step, FinishStep):
                history.append({"action": "finish", "answer": step.answer})
                return AgentRunResult(
                    status="completed",
                    task=task,
                    steps=_history_to_records(history),
                    final_answer=step.answer,
                    tools_used=list(tools_used),
                )

            if isinstance(step, ToolCallStep):
                if (
                    self.max_tool_calls is not None
                    and len(tools_used) >= self.max_tool_calls
                ):
                    return AgentRunResult(
                        status="error",
                        task=task,
                        steps=_history_to_records(history)
                        + [
                            StepRecord(
                                i,
                                "tool_limit",
                                {"name": step.name},
                                f"limite de {self.max_tool_calls} tool calls",
                            )
                        ],
                        abort_reason=f"limite de {self.max_tool_calls} tool calls",
                        tools_used=list(tools_used),
                    )
                record: dict[str, object] = {
                    "action": "tool",
                    "name": step.name,
                    "arguments": step.arguments,
                }
                try:
                    result = self.registry.run(step.name, step.arguments)
                    record["result"] = result
                    tools_used.append(step.name)
                except (KeyError, ValueError) as exc:
                    record["error"] = str(exc)
                    history.append(record)
                    return AgentRunResult(
                        status="error",
                        task=task,
                        steps=_history_to_records(history),
                        tools_used=list(tools_used),
                    )
                history.append(record)
                continue

        return AgentRunResult(
            status="max_steps",
            task=task,
            steps=_history_to_records(history),
            abort_reason=f"limite de {self.max_iterations} iterações",
            tools_used=list(tools_used),
        )


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