"""Registro de ferramentas YBY — somente search_knowledge, list_files, read_file."""

from __future__ import annotations

from pathlib import Path

from src.yby.rag.retrieve import RagRetriever
from src.yby.tools.base import ToolDefinition, ToolRegistry, ToolRisk
from src.yby.tools.file_tools import list_files_handler, read_file_handler
from src.yby.tools.knowledge_tools import SEARCH_KNOWLEDGE_META, search_knowledge_handler
from src.yby.tools.schemas import (
    ListFilesArgs,
    ListFilesOutput,
    ReadFileArgs,
    ReadFileOutput,
    SearchKnowledgeArgs,
    SearchKnowledgeOutput,
)
from src.yby.tools.security import default_read_roots

# Re-exports para compatibilidade (agente, testes legados)
from src.yby.tools.base import (  # noqa: F401
    ToolError,
    ToolResponse,
    audit_tool_call,
    run_handler_with_timeout,
)
from src.yby.tools.security import PathNotAllowedError, assert_allowed_path  # noqa: F401


def create_default_registry(
    *,
    read_roots: list[Path] | None = None,
    rag_retriever: RagRetriever | None = None,
    caller_access_level: str = "private",
) -> ToolRegistry:
    roots = read_roots or default_read_roots()
    retriever = rag_retriever or RagRetriever()
    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name=SEARCH_KNOWLEDGE_META["name"],
            description=SEARCH_KNOWLEDGE_META["description"],
            args_model=SearchKnowledgeArgs,
            output_model=SearchKnowledgeOutput,
            risk=SEARCH_KNOWLEDGE_META["risk"],
            requires_approval=SEARCH_KNOWLEDGE_META["requires_approval"],
            timeout_seconds=SEARCH_KNOWLEDGE_META["timeout_seconds"],
            handler=search_knowledge_handler(
                retriever,
                caller_access_level=caller_access_level,
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="list_files",
            description="Lista arquivos com extensão segura em diretórios allowlisted.",
            args_model=ListFilesArgs,
            output_model=ListFilesOutput,
            risk=ToolRisk.LOW,
            requires_approval=False,
            timeout_seconds=15.0,
            handler=list_files_handler(roots),
        )
    )
    registry.register(
        ToolDefinition(
            name="read_file",
            description=(
                "Lê trecho de arquivo allowlisted com extensão segura; "
                "limitado por max_bytes (nunca o arquivo inteiro por padrão)."
            ),
            args_model=ReadFileArgs,
            output_model=ReadFileOutput,
            risk=ToolRisk.MEDIUM,
            requires_approval=False,
            timeout_seconds=15.0,
            handler=read_file_handler(roots),
        )
    )
    return registry