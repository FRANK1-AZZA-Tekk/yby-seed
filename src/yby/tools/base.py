"""Contratos base do registro de ferramentas YBY."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from src.yby.rag.errors import RetrievalError
from src.yby.tools.security import PathNotAllowedError, UnsafeContentError, UnsafePathError

logger = logging.getLogger("yby.tools")

T = TypeVar("T", bound=BaseModel)


class ToolRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class ToolError:
    code: str
    message: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


@dataclass(frozen=True)
class ToolResponse:
    ok: bool
    tool: str
    data: dict[str, Any] | None
    error: ToolError | None
    duration_ms: float
    requires_approval: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "tool": self.tool,
            "data": self.data,
            "error": self.error.to_dict() if self.error else None,
            "duration_ms": round(self.duration_ms, 2),
            "requires_approval": self.requires_approval,
        }


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    args_model: type[BaseModel]
    output_model: type[BaseModel] | None
    risk: ToolRisk
    requires_approval: bool
    timeout_seconds: float
    handler: Callable[[BaseModel], dict[str, Any]]

    @property
    def json_schema(self) -> dict[str, Any]:
        return self.args_model.model_json_schema()

    @property
    def output_json_schema(self) -> dict[str, Any] | None:
        if self.output_model is None:
            return None
        return self.output_model.model_json_schema()

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "json_schema": self.json_schema,
            "output_json_schema": self.output_json_schema,
            "risk": self.risk.value,
            "requires_approval": self.requires_approval,
            "timeout_seconds": self.timeout_seconds,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"tool já registrada: {definition.name}")
        self._tools[definition.name] = definition

    def names(self) -> list[str]:
        return sorted(self._tools)

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def describe_all(self) -> list[dict[str, Any]]:
        return [self._tools[name].describe() for name in self.names()]

    def run(self, name: str, arguments: dict[str, Any], *, approved: bool = False) -> ToolResponse:
        started = time.perf_counter()
        spec = self._tools.get(name)
        if spec is None:
            return self._error_response(
                name,
                started,
                ToolError("tool_not_found", f"ferramenta não registrada: {name}"),
            )

        if spec.requires_approval and not approved:
            duration = (time.perf_counter() - started) * 1000
            response = ToolResponse(
                ok=False,
                tool=name,
                data=None,
                error=ToolError(
                    "approval_required",
                    "execução bloqueada até aprovação humana",
                ),
                duration_ms=duration,
                requires_approval=True,
            )
            audit_tool_call(name, arguments, response, justification="approval_gate")
            return response

        try:
            parsed = spec.args_model.model_validate(arguments)
        except ValidationError as exc:
            return self._error_response(
                name,
                started,
                ToolError(
                    "validation_error",
                    "argumentos inválidos",
                    details={"errors": exc.errors()},
                ),
                arguments=arguments,
            )

        try:
            data = run_handler_with_timeout(spec.handler, parsed, spec.timeout_seconds)
        except FuturesTimeoutError:
            return self._error_response(
                name,
                started,
                ToolError(
                    "timeout",
                    f"ferramenta excedeu {spec.timeout_seconds}s",
                ),
                arguments=arguments,
            )
        except PathNotAllowedError as exc:
            return self._error_response(
                name,
                started,
                ToolError("path_not_allowed", str(exc)),
                arguments=arguments,
            )
        except (UnsafePathError, UnsafeContentError) as exc:
            return self._error_response(
                name,
                started,
                ToolError("unsafe_path", str(exc)),
                arguments=arguments,
            )
        except FileNotFoundError as exc:
            return self._error_response(
                name,
                started,
                ToolError("not_found", str(exc)),
                arguments=arguments,
            )
        except RetrievalError as exc:
            return self._error_response(
                name,
                started,
                ToolError("execution_error", str(exc)),
                arguments=arguments,
            )
        except ValueError as exc:
            return self._error_response(
                name,
                started,
                ToolError("execution_error", str(exc)),
                arguments=arguments,
            )
        except Exception as exc:  # noqa: BLE001 — barreira para o LLM
            return self._error_response(
                name,
                started,
                ToolError(
                    "internal_error",
                    "falha na execução da ferramenta",
                    details={"type": exc.__class__.__name__},
                ),
                arguments=arguments,
            )

        duration = (time.perf_counter() - started) * 1000
        response = ToolResponse(
            ok=True,
            tool=name,
            data=data,
            error=None,
            duration_ms=duration,
        )
        audit_tool_call(name, arguments, response, justification="success")
        return response

    def _error_response(
        self,
        name: str,
        started: float,
        error: ToolError,
        *,
        requires_approval: bool = False,
        arguments: dict[str, Any] | None = None,
    ) -> ToolResponse:
        duration = (time.perf_counter() - started) * 1000
        response = ToolResponse(
            ok=False,
            tool=name,
            data=None,
            error=error,
            duration_ms=duration,
            requires_approval=requires_approval,
        )
        audit_tool_call(name, arguments or {}, response, justification=error.code)
        return response


def run_handler_with_timeout(
    handler: Callable[[BaseModel], dict[str, Any]],
    args: BaseModel,
    timeout_seconds: float,
) -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(handler, args)
        return future.result(timeout=timeout_seconds)


def audit_tool_call(
    tool: str,
    arguments: dict[str, Any],
    response: ToolResponse,
    *,
    justification: str,
) -> None:
    payload = {
        "event": "tool_call",
        "tool": tool,
        "ok": response.ok,
        "duration_ms": round(response.duration_ms, 2),
        "justification": justification,
        "argument_keys": sorted(arguments.keys()),
        "error_code": response.error.code if response.error else None,
    }
    logger.info("%s", json.dumps(payload, ensure_ascii=False))