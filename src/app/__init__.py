"""Application framework — Camada A (forma) + plugins B/C.

Núcleo fino + camadas empilháveis. Sem execução automática de código.
"""

from __future__ import annotations

from src.app.config import AppSettings, load_settings
from src.app.kernel import App, create_app
from src.app.layers import Layer, LayerRegistry, LayerStatus
from src.app.pipeline import CommandPipeline, LayerPlugin, default_pipeline

__all__ = [
    "App",
    "AppSettings",
    "CommandPipeline",
    "Layer",
    "LayerPlugin",
    "LayerRegistry",
    "LayerStatus",
    "create_app",
    "default_pipeline",
    "load_settings",
]
