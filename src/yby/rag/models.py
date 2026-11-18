"""Schemas Pydantic do RAG YBY."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

DocType = Literal["md", "txt", "pdf"]
AccessLevel = Literal["private", "team", "public"]


class RagConfig(BaseModel):
    """Valores de configuração validados para APIs e persistência leve."""

    knowledge_dir: str
    chroma_dir: str
    collection_name: str
    embed_model: str
    ollama_base_url: str
    chunk_size_tokens: int = Field(ge=64, le=8192)
    chunk_overlap_tokens: int = Field(ge=0)
    default_top_k: int = Field(ge=1, le=50)
    max_results: int = Field(ge=1, le=50)
    timeout_seconds: float = Field(gt=0)


class DocumentMetadata(BaseModel):
    """Metadados obrigatórios por documento/chunk indexado."""

    source: str = Field(min_length=1)
    title: str = Field(min_length=1)
    doc_type: DocType
    language: str = Field(min_length=2, max_length=16)
    created_at: datetime
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)
    access_level: AccessLevel = "private"
    chunk_index: int = Field(ge=0)
    chunk_total: int = Field(ge=1)
    content_hash: str = Field(min_length=64, max_length=64)

    @field_validator("content_hash")
    @classmethod
    def _hex_sha256(cls, value: str) -> str:
        if any(char not in "0123456789abcdef" for char in value.lower()):
            raise ValueError("content_hash deve ser SHA-256 em hexadecimal")
        return value.lower()

    @model_validator(mode="after")
    def _chunk_bounds(self) -> DocumentMetadata:
        if self.chunk_index >= self.chunk_total:
            raise ValueError("chunk_index deve ser < chunk_total")
        return self


class KnowledgeChunk(BaseModel):
    """Chunk de texto + metadados (unidade de índice)."""

    text: str = Field(min_length=1)
    metadata: DocumentMetadata


class RetrievalResult(BaseModel):
    """Um hit de busca semântica (campos estruturados + metadados brutos opcionais)."""

    text: str
    score: float
    source: str
    title: str = ""
    doc_type: DocType | str = ""
    tags: list[str] = Field(default_factory=list)
    access_level: AccessLevel | str = "private"
    chunk_index: int = Field(ge=0, default=0)
    chunk_total: int = Field(ge=1, default=1)
    content_hash: str = ""
    language: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResponse(BaseModel):
    """Resposta agregada de consulta."""

    query: str
    hits: list[RetrievalResult]
    context_text: str = ""
    context_chars: int = Field(ge=0)
    truncated: bool = False
    filters: dict[str, Any] = Field(default_factory=dict)


class IngestionResult(BaseModel):
    """Resultado de ingestão de um arquivo."""

    source: str
    skipped: bool
    chunks_indexed: int = Field(ge=0)
    content_hash: str = Field(min_length=64, max_length=64)


class IngestionError(BaseModel):
    """Erro de ingestão serializável (não substitui src.yby.rag.errors.IngestionError)."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, Any] | None = None