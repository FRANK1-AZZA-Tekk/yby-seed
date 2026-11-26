"""Contratos (ports) do pipeline de reuso, histórico e cache do YBY Machine."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from src.yby_machine.spec import YBYSpec

if TYPE_CHECKING:
    from src.yby_machine.translator import TranslateResult


class AppSummary(BaseModel):
    """Resumo listado em GET /api/machine/apps."""

    app_id: str = Field(min_length=1)
    name: str
    title: str
    description: str = ""
    created_at: str


class StoredAppRecord(BaseModel):
    """Spec persistida com metadados para reuso e consulta por app_id."""

    app_id: str = Field(min_length=1)
    prompt: str
    spec: YBYSpec
    source: str
    created_at: str
    similarity: float | None = None

    def to_summary(self) -> AppSummary:
        return AppSummary(
            app_id=self.app_id,
            name=self.spec.name,
            title=self.spec.title,
            description=self.spec.description,
            created_at=self.created_at,
        )


@runtime_checkable
class EmbedderPort(Protocol):
    """Gera vetor numérico para busca por similaridade de prompts."""

    async def embed(self, text: str) -> list[float]: ...

    async def close(self) -> None: ...


@runtime_checkable
class SpecStorePort(Protocol):
    """Persiste specs geradas e permite reuso por similaridade e histórico."""

    async def find_similar(
        self,
        embedding: list[float],
        *,
        min_similarity: float = 0.92,
    ) -> StoredAppRecord | None: ...

    async def save(
        self,
        *,
        prompt: str,
        embedding: list[float],
        spec: YBYSpec,
        source: str,
    ) -> StoredAppRecord: ...

    async def list_apps(self, *, limit: int = 50) -> list[AppSummary]: ...

    async def get_app(self, app_id: str) -> StoredAppRecord | None: ...

    async def close(self) -> None: ...


@runtime_checkable
class TranslateCachePort(Protocol):
    """Cache de traduções por fingerprint do prompt (memória ou Redis opcional)."""

    async def get(self, prompt: str) -> TranslateResult | None: ...

    async def put(self, prompt: str, result: TranslateResult) -> None: ...

    async def close(self) -> None: ...
