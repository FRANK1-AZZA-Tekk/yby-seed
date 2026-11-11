"""Registro de camadas empilháveis do produto."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Layer(StrEnum):
    """Camadas do roadmap de produto (A→D antes de API/UI)."""

    FORM = "A"  # forma: entrypoint + kernel
    BRIEFING = "B"  # briefing revisável
    SKILLS = "C"  # skills dry-run
    MEMORY = "D"  # memória local


class LayerStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    PLANNED = "planned"
    FROZEN = "frozen"  # scaffold fora do MVP


@dataclass(frozen=True)
class LayerInfo:
    layer: Layer
    name: str
    status: LayerStatus
    summary: str
    entry: str


class LayerRegistry:
    """Estado declarado das camadas — fonte única para `status` / `/layers`."""

    def __init__(self) -> None:
        self._layers: tuple[LayerInfo, ...] = (
            LayerInfo(
                layer=Layer.FORM,
                name="Forma do produto",
                status=LayerStatus.READY,
                summary="Kernel + CLI unificada + REPL (Camada A)",
                entry="python yby_seed.py | python src/main.py run",
            ),
            LayerInfo(
                layer=Layer.BRIEFING,
                name="Briefing revisável",
                status=LayerStatus.READY,
                summary="Pedido → perguntas → export MD/JSON (sem exec. de código)",
                entry="python src/main.py brief | /brief no REPL",
            ),
            LayerInfo(
                layer=Layer.SKILLS,
                name="Skills dry-run",
                status=LayerStatus.PARTIAL,
                summary="Discovery + dry-run preview; sem execução de código",
                entry="/skills | /skill <nome> | python yby_seed.py skills",
            ),
            LayerInfo(
                layer=Layer.MEMORY,
                name="Memória local",
                status=LayerStatus.PLANNED,
                summary="Arquivos em .yby/ (Qdrant fica pós-MVP)",
                entry="(ainda não)",
            ),
        )

    def all(self) -> tuple[LayerInfo, ...]:
        return self._layers

    def get(self, layer: Layer) -> LayerInfo:
        for info in self._layers:
            if info.layer == layer:
                return info
        raise KeyError(layer)

    def format_table(self) -> str:
        lines = ["Camada | Status   | Nome", "-" * 56]
        for info in self._layers:
            lines.append(
                f"{info.layer.value:6} | {info.status.value:8} | {info.name} — {info.summary}"
            )
        return "\n".join(lines)
