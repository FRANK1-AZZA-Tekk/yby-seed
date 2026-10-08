"""Testes do RAG (LanceDB + AST Chunking + Context Pruning).

Estes testes dependem de embeddings reais e LanceDB configurado.
Por enquanto, estão marcados como skip até que fixtures reais sejam implementadas.
"""

import pytest


@pytest.mark.skip(reason="RAG depende de embeddings reais - fixtures pendentes")
@pytest.mark.integration
async def test_rag_chunking_ast(sample_skill_manifest, mock_lancedb):
    """RAG deve fazer chunking do código em AST."""
    # TODO: Implementar testes reais quando fixtures estiverem prontas
    pass


@pytest.mark.skip(reason="RAG depende de embeddings reais - fixtures pendentes")
@pytest.mark.integration
async def test_rag_context_pruning(sample_user_command, mock_lancedb):
    """RAG deve reduzir tokens injetados via Context Pruning."""
    # TODO: Implementar testes reais quando fixtures estiverem prontas
    pass


@pytest.mark.skip(reason="RAG depende de embeddings reais - fixtures pendentes")
@pytest.mark.integration
async def test_rag_recupera_contexto_relevante(sample_user_command, mock_lancedb):
    """RAG deve recuperar contexto relevante para o comando."""
    # TODO: Implementar testes reais quando fixtures estiverem prontas
    pass
