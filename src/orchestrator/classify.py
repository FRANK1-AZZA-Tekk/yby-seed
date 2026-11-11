"""Classificação determinística de tarefa (origem: yby-core/graph.py)."""

from typing import Literal

TaskType = Literal["chat", "firmware", "research", "memory", "hardware"]


def classify_task(message: str) -> TaskType:
    text = message.lower()

    if any(word in text for word in ("esp32", "firmware", "platformio", "t-watch")):
        return "firmware"
    if any(word in text for word in ("pesquise", "compare", "preço", "preco")):
        return "research"
    if any(word in text for word in ("memória", "memoria", "documento", "manual")):
        return "memory"
    if any(word in text for word in ("hardware", "vram", "gtx", "bateria")):
        return "hardware"
    return "chat"
