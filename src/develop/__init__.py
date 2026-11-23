"""Develop — piloto Ollama → Markdown → Cursor (multi-camada, sem OpenRouter)."""

__all__ = ["DevelopPlan"]


def __getattr__(name: str):
    if name == "DevelopPlan":
        from src.develop.schemas import DevelopPlan

        return DevelopPlan
    raise AttributeError(name)
