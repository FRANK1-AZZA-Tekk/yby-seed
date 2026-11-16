"""Schemas Pydantic de entrada e saída das ferramentas YBY."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator

from src.yby.rag.retrieve import DEFAULT_MAX_CONTEXT_CHARS


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    doc_type: Literal["md", "txt", "pdf"] | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)
    access_level: Literal["private", "team", "public"] | None = None
    max_context_chars: int = Field(
        default=DEFAULT_MAX_CONTEXT_CHARS,
        ge=100,
        le=20_000,
    )


class KnowledgeHitOut(BaseModel):
    text: str
    score: float
    source: str
    title: str = ""
    doc_type: str = ""
    tags: list[str] = Field(default_factory=list)
    access_level: str = "private"
    chunk_index: int = 0
    chunk_total: int = 1
    content_hash: str = ""
    language: str = ""


class SearchKnowledgeOutput(BaseModel):
    query: str
    hits: list[KnowledgeHitOut]
    context_text: str
    context_chars: int = Field(ge=0)
    truncated: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


class ListFilesArgs(BaseModel):
    directory: str = Field(
        default=".",
        min_length=1,
        max_length=4096,
        validation_alias=AliasChoices("directory", "path"),
    )
    pattern: str = Field(default="*", min_length=1, max_length=128)
    max_entries: int = Field(default=100, ge=1, le=500)

    @field_validator("directory")
    @classmethod
    def _no_traversal(cls, value: str) -> str:
        if ".." in value.replace("\\", "/").split("/"):
            raise ValueError("directory não pode conter ..")
        return value


class FileEntryOut(BaseModel):
    path: str
    name: str
    size_bytes: int = Field(ge=0)
    extension: str


class ListFilesOutput(BaseModel):
    directory: str
    entries: list[FileEntryOut]
    truncated: bool = False


class ReadFileArgs(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    max_bytes: int = Field(default=65_536, ge=1, le=512_000)
    encoding: str = Field(default="utf-8", min_length=1, max_length=32)

    @field_validator("path")
    @classmethod
    def _no_traversal(cls, value: str) -> str:
        if ".." in value.replace("\\", "/").split("/"):
            raise ValueError("path não pode conter ..")
        return value


class ReadFileOutput(BaseModel):
    path: str
    size_bytes: int = Field(ge=0)
    read_bytes: int = Field(ge=0)
    truncated: bool = False
    encoding: str
    content: str