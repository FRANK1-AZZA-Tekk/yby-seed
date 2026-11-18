"""Exceções do RAG YBY (camada de fundação)."""

from __future__ import annotations


class RagError(Exception):
    """Erro base do subsistema RAG."""


class ConfigurationError(RagError, ValueError):
    """Configuração inválida ou variáveis de ambiente inconsistentes."""


class IngestionError(RagError):
    """Falha na ingestão de documentos."""


class RetrievalError(RagError):
    """Falha na consulta ao índice vetorial."""


class UnsupportedDocumentError(IngestionError):
    """Tipo de arquivo ou conteúdo não suportado para indexação."""