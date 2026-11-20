"""Schemas do plano develop (status PT alinhados ao painel)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

LayerStatus = Literal["preparada", "enviada", "aceita", "rejeitada"]


class Layer(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    depends_on: list[str] = Field(default_factory=list)
    objetivo: str = Field(min_length=1, max_length=4000)
    allowed_files: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)
    status: LayerStatus = "preparada"
    optional_patch: str | None = None  # texto apenas — nunca aplicado


class DevelopPlan(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    pedido: str = Field(default="", max_length=8000)
    base_commit: str = Field(default="", max_length=64)
    updated_at: float = 0.0
    layers: list[Layer] = Field(default_factory=list)

    def layer(self, layer_id: str) -> Layer | None:
        for item in self.layers:
            if item.id == layer_id:
                return item
        return None

    def to_painel_dict(self) -> dict[str, Any]:
        """Formato mínimo lido pelo painel + campos extras inócuos."""

        return self.model_dump()
