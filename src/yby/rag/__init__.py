"""RAG local (ingestão e consulta)."""

from src.yby.rag.ingest import (
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
    DEFAULT_ACCESS_LEVEL,
    DEFAULT_CHROMA_DIR,
    DEFAULT_COLLECTION_NAME,
    DEFAULT_EMBED_MODEL,
    IngestResult,
    RagIngestor,
    ingest_paths,
)
from src.yby.rag.retrieve import (
    DEFAULT_MAX_CONTEXT_CHARS,
    DEFAULT_TOP_K,
    RagRetriever,
    RetrieveHit,
    RetrieveResult,
    search_knowledge,
)

__all__ = [
    "CHUNK_OVERLAP_TOKENS",
    "CHUNK_SIZE_TOKENS",
    "DEFAULT_ACCESS_LEVEL",
    "DEFAULT_CHROMA_DIR",
    "DEFAULT_COLLECTION_NAME",
    "DEFAULT_EMBED_MODEL",
    "DEFAULT_MAX_CONTEXT_CHARS",
    "DEFAULT_TOP_K",
    "IngestResult",
    "RagIngestor",
    "RagRetriever",
    "RetrieveHit",
    "RetrieveResult",
    "ingest_paths",
    "search_knowledge",
]