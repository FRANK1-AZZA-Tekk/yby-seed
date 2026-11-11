"""Protocolo de plugins de camada — registrar handlers sem hardcoding eterno."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from src.app.layers import Layer

if TYPE_CHECKING:
    from src.app.kernel import App


@runtime_checkable
class LayerPlugin(Protocol):
    """Plugin empilhável: uma camada registra seus comandos no kernel."""

    layer: Layer
    name: str

    def register(self, app: App) -> None:
        """Instala comandos / handlers nesta App."""
        ...


class CommandPipeline:
    """Lista ordenada de plugins instalados no kernel."""

    def __init__(self) -> None:
        self._plugins: list[LayerPlugin] = []

    def add(self, plugin: LayerPlugin) -> CommandPipeline:
        self._plugins.append(plugin)
        return self

    def install(self, app: App) -> None:
        for plugin in self._plugins:
            plugin.register(app)

    def plugins(self) -> tuple[LayerPlugin, ...]:
        return tuple(self._plugins)


def default_pipeline() -> CommandPipeline:
    """Pipeline padrão do produto (camadas além do núcleo A)."""
    from src.app.skills_layer import SkillsLayer

    return CommandPipeline().add(SkillsLayer())
