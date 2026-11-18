"""Ferramenta search_knowledge (RAG local)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from src.yby.rag.retrieve import RagRetriever, RetrieveHit
from src.yby.tools.base import ToolRisk
from src.yby.tools.schemas import SearchKnowledgeArgs, SearchKnowledgeOutput


def search_knowledge_handler(
    retriever: RagRetriever,
    *,
    caller_access_level: str = "private",
) -> Callable[[BaseModel], dict[str, Any]]:
    def handler(args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, SearchKnowledgeArgs)
        result = retriever.search(
            args.query,
            top_k=args.top_k,
            doc_type=args.doc_type,
            tags=args.tags or None,
            access_level=args.access_level,
            max_context_chars=args.max_context_chars,
            caller_access_level=caller_access_level,
        )
        hits = [_hit_to_out(hit) for hit in result.hits]
        payload = SearchKnowledgeOutput(
            query=result.query,
            hits=hits,
            context_text=result.context_text,
            context_chars=result.context_chars,
            truncated=result.truncated,
            meta=result.metadata,
        )
        return payload.model_dump()

    return handler


def _hit_to_out(hit: RetrieveHit) -> dict[str, Any]:
    from src.yby.tools.schemas import KnowledgeHitOut

    return KnowledgeHitOut(
        text=hit.text,
        score=hit.score,
        source=hit.source,
        title=hit.title,
        doc_type=hit.doc_type,
        tags=list(hit.tags),
        access_level=hit.access_level,
        chunk_index=hit.chunk_index,
        chunk_total=hit.chunk_total,
        content_hash=hit.content_hash,
        language=hit.language,
    ).model_dump()


SEARCH_KNOWLEDGE_META = {
    "name": "search_knowledge",
    "description": (
        "Busca semântica no índice RAG local (somente chunks indexados; "
        "não retorna documentos inteiros do disco)."
    ),
    "args_model": SearchKnowledgeArgs,
    "output_model": SearchKnowledgeOutput,
    "risk": ToolRisk.LOW,
    "requires_approval": False,
    "timeout_seconds": 60.0,
}