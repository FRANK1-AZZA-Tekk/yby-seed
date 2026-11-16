"""Camada de explicação em português (modo professor). Não executa nada."""

from src.conversation.explain import (
    ExplainBlocks,
    clarify_questions,
    format_blocks,
    format_cli_error,
    format_command_decision,
    format_engine_reply,
    format_vague_ask,
    is_vague_request,
)

__all__ = [
    "ExplainBlocks",
    "clarify_questions",
    "format_blocks",
    "format_cli_error",
    "format_command_decision",
    "format_engine_reply",
    "format_vague_ask",
    "is_vague_request",
]
