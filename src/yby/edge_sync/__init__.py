"""Módulo D — Ponte de sincronização Edge (Xiaomi 12 Termux -> PostgreSQL + pgvector)."""

from __future__ import annotations

from src.yby.edge_sync.api import create_edge_sync_router
from src.yby.edge_sync.schemas import (
    EMBEDDING_DIM,
    EdgeEvent,
    EdgeSyncBatchRequest,
    EdgeSyncBatchResponse,
    EdgeSyncStatus,
    StoredEdgeEvent,
)
from src.yby.edge_sync.store import (
    PgVectorEdgeStore,
    SQLiteFallbackEdgeStore,
    VectorEventStore,
)
from src.yby.edge_sync.worker import (
    EdgeSyncWorker,
    EmbeddingProvider,
    OllamaEmbeddingProvider,
)

__all__ = [
    "EMBEDDING_DIM",
    "EdgeEvent",
    "EdgeSyncBatchRequest",
    "EdgeSyncBatchResponse",
    "EdgeSyncStatus",
    "EdgeSyncWorker",
    "EmbeddingProvider",
    "OllamaEmbeddingProvider",
    "PgVectorEdgeStore",
    "SQLiteFallbackEdgeStore",
    "StoredEdgeEvent",
    "VectorEventStore",
    "create_edge_sync_router",
]
