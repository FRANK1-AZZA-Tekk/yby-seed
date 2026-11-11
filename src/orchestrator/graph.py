"""Grafo LangGraph opcional.

O núcleo do YBY SEED usa `classify_task` + `choose_model` sem LangGraph.
A implementação completa com ToolNode vive em `integrations/yby-core/`
(espelho do repositório yby-core) e exige:

    pip install -r integrations/yby-core/requirements.txt
"""

from __future__ import annotations

from typing import Any


def build_yby_graph() -> Any:
    try:
        from integrations.yby_core.app.graph import yby_graph
    except ImportError as exc:  # pragma: no cover - caminho opcional
        raise ImportError(
            "Grafo LangGraph indisponível. Use src.orchestrator.classify/choose_model "
            "ou instale as dependências em integrations/yby-core/requirements.txt"
        ) from exc
    return yby_graph
