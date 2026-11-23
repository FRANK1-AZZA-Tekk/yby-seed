"""Registro da rota yby-vision no LiteLLM (sem fallback em cascata)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

DEFAULT_VISION_HOST = "127.0.0.1"
DEFAULT_VISION_PORT = 8100
VISION_MODEL_NAME = "yby-vision"


def _vision_entry(*, host: str, port: int) -> dict[str, Any]:
    return {
        "model_name": VISION_MODEL_NAME,
        "litellm_params": {
            "model": "openai/yby-vision",
            "api_base": f"http://{host}:{port}/v1",
        },
    }


def register_fusion_route(
    config: dict[str, Any],
    *,
    host: str = DEFAULT_VISION_HOST,
    port: int = DEFAULT_VISION_PORT,
) -> dict[str, Any]:
    """
    Adiciona o alias ``yby-vision`` apontando para o servidor FastAPI local.

    Não altera ``router_settings.fallbacks`` — visão fica fora da pirâmide de texto.

    Args:
        config: Dicionário no formato de ``litellm_config.yaml`` (model_list, etc.).
        host: Host do servidor FUSION (padrão loopback).
        port: Porta do servidor FUSION (padrão 8100).

    Returns:
        Cópia do config com a entrada ``yby-vision`` (ou substituição se já existir).
    """
    updated = deepcopy(config)
    model_list: list[dict[str, Any]] = list(updated.get("model_list") or [])
    entry = _vision_entry(host=host, port=port)

    replaced = False
    for index, item in enumerate(model_list):
        if item.get("model_name") == VISION_MODEL_NAME:
            model_list[index] = entry
            replaced = True
            break
    if not replaced:
        model_list.append(entry)

    updated["model_list"] = model_list
    return updated