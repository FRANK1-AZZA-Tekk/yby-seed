"""Embeddings locais via Ollama."""

from __future__ import annotations

from llama_index.core import Settings
from llama_index.core.embeddings import BaseEmbedding
from llama_index.embeddings.ollama import OllamaEmbedding

from src.yby.rag.config import RagConfig


def create_embedder(
    config: RagConfig,
    *,
    override: BaseEmbedding | None = None,
) -> BaseEmbedding:
    model = override or OllamaEmbedding(
        model_name=config.embed_model,
        base_url=config.ollama_base_url,
        request_timeout=config.timeout_seconds,
    )
    Settings.embed_model = model
    return model