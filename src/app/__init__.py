"""Application framework — Camada A (forma do produto).

Núcleo fino + camadas empilháveis. Sem execução automática de código.
"""

from __future__ import annotations

from src.app.config import AppSettings, load_settings
from src.app.kernel import App, create_app
from src.app.layers import Layer, LayerRegistry, LayerStatus

__all__ = [
    "App",
    "AppSettings",
    "Layer",
    "LayerRegistry",
    "LayerStatus",
    "create_app",
    "load_settings",
]
