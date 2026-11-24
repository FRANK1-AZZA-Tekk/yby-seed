"""DTOs do painel — estados distintos, sem HTML."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ItemState = Literal["proposto", "executado", "falhou", "aguardando_aprovacao"]


@dataclass(frozen=True)
class PainelItem:
    origin: str
    timestamp: float
    state: ItemState
    title: str
    detail: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PainelResumo:
    ollama: str
    routines: list[PainelItem]
    alerts: list[PainelItem]
    reminders: list[PainelItem]
    develop_layers: list[PainelItem]

    def to_dict(self) -> dict[str, Any]:
        def _item(it: PainelItem) -> dict[str, Any]:
            return {
                "origin": it.origin,
                "timestamp": it.timestamp,
                "state": it.state,
                "title": it.title,
                "detail": it.detail,
                "meta": it.meta,
            }

        return {
            "ollama": self.ollama,
            "routines": [_item(x) for x in self.routines],
            "alerts": [_item(x) for x in self.alerts],
            "reminders": [_item(x) for x in self.reminders],
            "develop_layers": [_item(x) for x in self.develop_layers],
        }
