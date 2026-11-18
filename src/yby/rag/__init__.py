"""RAG local YBY."""

from src.yby.rag.config import RagConfig
from src.yby.rag.errors import (
    ConfigurationError,
    IngestionError as IngestionErrorException,
    RagError,
    RetrievalError,
    UnsupportedDocumentError,
)
from src.yby.rag.models import (
    DocumentMetadata,
    IngestionError,
    IngestionResult,
    KnowledgeChunk,
    RagConfig as RagConfigSchema,
    RetrievalResponse,
    RetrievalResult,
)

# Compatibilidade com implementações posteriores (T2–T5); não fazem parte da Tarefa 1.
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
    "ConfigurationError",
    "DocumentMetadata",
    "IngestionError",
    "IngestionErrorException",
    "IngestionResult",
    "KnowledgeChunk",
    "RagConfig",
    "RagConfigSchema",
    "RagError",
    "RetrievalError",
    "RetrievalResponse",
    "RetrievalResult",
    "UnsupportedDocumentError",
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