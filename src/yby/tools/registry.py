"""Registro de ferramentas YBY com contrato, validação e log estruturado."""

from __future__ import annotations

import fnmatch
import json
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, Field, ValidationError

from src.yby.rag.retrieve import DEFAULT_MAX_CONTEXT_CHARS, RagRetriever, RetrieveHit
from src.yby.tools.allowlist import PathNotAllowedError, assert_allowed_path, default_read_roots

logger = logging.getLogger("yby.tools")

T = TypeVar("T", bound=BaseModel)


class ToolRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    doc_type: Literal["md", "txt", "pdf"] | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)
    access_level: str | None = Field(default=None, max_length=64)
    max_context_chars: int = Field(
        default=DEFAULT_MAX_CONTEXT_CHARS,
        ge=100,
        le=20_000,
    )


class ListFilesArgs(BaseModel):
    path: str = Field(default=".", min_length=1, max_length=4096)
    pattern: str = Field(default="*", min_length=1, max_length=128)
    max_entries: int = Field(default=100, ge=1, le=500)


class ReadFileArgs(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    max_bytes: int = Field(default=65_536, ge=1, le=512_000)


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
    risk: ToolRisk
    requires_approval: bool
    timeout_seconds: float
    handler: Callable[[BaseModel], dict[str, Any]]

    @property
    def json_schema(self) -> dict[str, Any]:
        return self.args_model.model_json_schema()

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "json_schema": self.json_schema,
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
            _log_tool_call(name, arguments, response, justification="approval_gate")
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
            )

        try:
            data = _run_with_timeout(spec.handler, parsed, spec.timeout_seconds)
        except FuturesTimeoutError:
            return self._error_response(
                name,
                started,
                ToolError(
                    "timeout",
                    f"ferramenta excedeu {spec.timeout_seconds}s",
                ),
            )
        except PathNotAllowedError as exc:
            return self._error_response(
                name,
                started,
                ToolError("path_not_allowed", str(exc)),
            )
        except FileNotFoundError as exc:
            return self._error_response(
                name,
                started,
                ToolError("not_found", str(exc)),
            )
        except ValueError as exc:
            return self._error_response(
                name,
                started,
                ToolError("execution_error", str(exc)),
            )

        duration = (time.perf_counter() - started) * 1000
        response = ToolResponse(
            ok=True,
            tool=name,
            data=data,
            error=None,
            duration_ms=duration,
        )
        _log_tool_call(name, arguments, response, justification="success")
        return response

    def _error_response(
        self,
        name: str,
        started: float,
        error: ToolError,
        *,
        requires_approval: bool = False,
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
        _log_tool_call(name, {}, response, justification=error.code)
        return response


def create_default_registry(
    *,
    read_roots: list[Path] | None = None,
    rag_retriever: RagRetriever | None = None,
) -> ToolRegistry:
    roots = read_roots or default_read_roots()
    retriever = rag_retriever or RagRetriever()
    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="search_knowledge",
            description=(
                "Busca semântica no índice RAG local (somente chunks; "
                "não envia documentos inteiros)."
            ),
            args_model=SearchKnowledgeArgs,
            risk=ToolRisk.LOW,
            requires_approval=False,
            timeout_seconds=60.0,
            handler=_search_knowledge_factory(retriever),
        )
    )
    registry.register(
        ToolDefinition(
            name="list_files",
            description="Lista arquivos em diretórios allowlisted (somente leitura).",
            args_model=ListFilesArgs,
            risk=ToolRisk.LOW,
            requires_approval=False,
            timeout_seconds=15.0,
            handler=_list_files_factory(roots),
        )
    )
    registry.register(
        ToolDefinition(
            name="read_file",
            description=(
                "Lê trecho de arquivo em diretório allowlisted; "
                "limitado por max_bytes (nunca o arquivo inteiro por padrão)."
            ),
            args_model=ReadFileArgs,
            risk=ToolRisk.MEDIUM,
            requires_approval=False,
            timeout_seconds=15.0,
            handler=_read_file_factory(roots),
        )
    )
    return registry


def _run_with_timeout(
    handler: Callable[[BaseModel], dict[str, Any]],
    args: BaseModel,
    timeout_seconds: float,
) -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(handler, args)
        return future.result(timeout=timeout_seconds)


def _search_knowledge_factory(retriever: RagRetriever) -> Callable[[BaseModel], dict[str, Any]]:
    def handler(args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, SearchKnowledgeArgs)
        result = retriever.search(
            args.query,
            top_k=args.top_k,
            doc_type=args.doc_type,
            tags=args.tags or None,
            access_level=args.access_level,
            max_context_chars=args.max_context_chars,
        )
        return {
            "hits": [_hit_to_dict(hit) for hit in result.hits],
            "context_text": result.context_text,
            "context_chars": result.context_chars,
            "truncated": result.truncated,
            "query": result.query,
            "meta": result.metadata,
        }

    return handler


def _list_files_factory(roots: list[Path]) -> Callable[[BaseModel], dict[str, Any]]:
    def handler(args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, ListFilesArgs)
        directory = assert_allowed_path(args.path, roots=roots)
        if not directory.is_dir():
            raise ValueError("path não é um diretório")

        entries: list[dict[str, Any]] = []
        for child in sorted(directory.iterdir()):
            if not fnmatch.fnmatch(child.name, args.pattern):
                continue
            entries.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "is_dir": child.is_dir(),
                }
            )
            if len(entries) >= args.max_entries:
                break

        return {
            "directory": str(directory),
            "entries": entries,
            "truncated": len(entries) >= args.max_entries,
        }

    return handler


def _read_file_factory(roots: list[Path]) -> Callable[[BaseModel], dict[str, Any]]:
    def handler(args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, ReadFileArgs)
        file_path = assert_allowed_path(args.path, roots=roots)
        if not file_path.is_file():
            raise FileNotFoundError(f"arquivo inexistente: {file_path}")

        size = file_path.stat().st_size
        with file_path.open("rb") as handle:
            raw = handle.read(args.max_bytes)

        truncated = size > len(raw)
        text = raw.decode("utf-8", errors="replace")
        return {
            "path": str(file_path),
            "size_bytes": size,
            "read_bytes": len(raw),
            "truncated": truncated,
            "content": text,
        }

    return handler


def _hit_to_dict(hit: RetrieveHit) -> dict[str, Any]:
    return {
        "text": hit.text,
        "score": hit.score,
        "source": hit.source,
        "metadata": hit.metadata,
    }


def _log_tool_call(
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