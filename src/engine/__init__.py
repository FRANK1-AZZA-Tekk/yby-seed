"""Motor híbrido do YBY SEED: Ollama local; nuvem só quando o roteamento pede."""

from src.engine.hybrid import EngineReply, HybridEngine, engine_from_env

__all__ = ["EngineReply", "HybridEngine", "engine_from_env"]
