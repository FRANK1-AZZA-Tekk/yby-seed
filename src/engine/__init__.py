"""Motor híbrido do YBY SEED: Ollama local e fallback OpenAI-compatível."""

from src.engine.hybrid import EngineReply, HybridEngine, engine_from_env

__all__ = ["EngineReply", "HybridEngine", "engine_from_env"]
