"""
RAG Optimizer — retrieval local otimizado para 4GB VRAM.

Sem instância global no import. Embeddings reais via OllamaClient.embed().
LanceDB/tree-sitter são lazy.
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.ollama_client import OllamaClient, OllamaError
from src.rag.ast_chunker import get_ast_chunker
from src.rag.context_pruner import context_pruner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGOptimizer:
    """RAG completo otimizado para Edge AI."""

    def __init__(
        self,
        db_path: str = "/data/vectors",
        ollama: OllamaClient | None = None,
    ):
        self.db_path = db_path
        self.ollama = ollama or OllamaClient()
        self._owns_client = ollama is None
        self._db = None
        self._chunker = None

    @property
    def db(self):
        if self._db is None:
            from src.gateway.lancedb_client import LanceDBClient

            self._db = LanceDBClient(self.db_path, index_cache_size=128)
        return self._db

    @property
    def chunker(self):
        if self._chunker is None:
            self._chunker = get_ast_chunker("python")
        return self._chunker

    async def index_document(
        self, doc_text: str, doc_id: str, metadata: dict[str, Any]
    ) -> None:
        logger.info("📚 Indexando documento: %s", doc_id)
        chunks = self.chunker.chunk(doc_text, max_tokens=512)

        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            embedding = await self._generate_embedding(chunk["code"])
            await self.db.insert_vector(
                {
                    "id": chunk_id,
                    "device_id": doc_id,
                    "timestamp": "2026-10-08T05:20:00Z",
                    "text": chunk["code"],
                    "vector": embedding,
                    "metadata": str({**metadata, **chunk}),
                }
            )

        logger.info("✅ %s chunks indexados", len(chunks))

    async def search(
        self, query: str, top_k: int = 10, max_context_tokens: int = 2000
    ) -> list[str]:
        logger.info("🔍 Buscando RAG: %s", query)
        query_embedding = await self._generate_embedding(query)
        results = await self.db.search(query_embedding, top_k=top_k)
        chunks = [r["text"] for r in results]
        pruned_chunks = context_pruner.prune(
            chunks, query, max_tokens=max_context_tokens
        )
        logger.info("✅ %s chunks relevantes", len(pruned_chunks))
        return pruned_chunks

    async def _generate_embedding(self, text: str) -> list[float]:
        """Embedding real via Ollama — nunca retorna vetor fictício."""
        vectors = self.ollama.embed(text)
        if not vectors or not vectors[0]:
            raise OllamaError("Embedding vazio")
        return vectors[0]

    async def rag_query(
        self, query: str, max_context_tokens: int = 2000
    ) -> dict[str, Any]:
        logger.info("🧠 RAG query: %s", query)
        chunks = await self.search(
            query, top_k=10, max_context_tokens=max_context_tokens
        )
        context = "\n\n".join(chunks)
        prompt = f"""
Use o contexto abaixo para responder a query:

Contexto:
{context}

Query: {query}

Resposta:
"""
        answer = self.ollama.generate(
            model="llama3.2:3b",
            prompt=prompt,
            options={"temperature": 0.2, "num_predict": 512},
        )
        return {
            "answer": answer,
            "chunks_used": chunks,
            "context_tokens": len(context.split()),
        }

    def close(self) -> None:
        if self._owns_client:
            self.ollama.close()


def get_rag_optimizer(
    db_path: str = "/data/vectors", ollama: OllamaClient | None = None
) -> RAGOptimizer:
    return RAGOptimizer(db_path=db_path, ollama=ollama)
