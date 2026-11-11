"""
Configurações centralizadas do Gateway YBY SEED.

Settings via dataclass + os.getenv — sem pydantic-settings
(evita quebrar import no MVP / Phase 0–1).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    """Configurações do Gateway."""

    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_CLIENT_ID: str = "yby-seed-gateway"
    MQTT_TOPIC_PREFIX: str = "yby"

    LANCEDB_PATH: str = "/data/vectors"
    LANCEDB_INDEX_CACHE_SIZE: int = 128

    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL_EMBEDDING: str = "all-minilm"
    OLLAMA_MODEL_LLM: str = "llama3.2:3b"

    FASTAPI_HOST: str = "127.0.0.1"
    FASTAPI_PORT: int = 8000
    FASTAPI_WORKERS: int = 1

    LOG_LEVEL: str = "INFO"
    API_KEY: str | None = None

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            MQTT_BROKER_HOST=os.getenv("MQTT_BROKER_HOST", "localhost"),
            MQTT_BROKER_PORT=_env_int("MQTT_BROKER_PORT", 1883),
            MQTT_CLIENT_ID=os.getenv("MQTT_CLIENT_ID", "yby-seed-gateway"),
            MQTT_TOPIC_PREFIX=os.getenv("MQTT_TOPIC_PREFIX", "yby"),
            LANCEDB_PATH=os.getenv("LANCEDB_PATH", "/data/vectors"),
            LANCEDB_INDEX_CACHE_SIZE=_env_int("LANCEDB_INDEX_CACHE_SIZE", 128),
            OLLAMA_HOST=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            OLLAMA_MODEL_EMBEDDING=os.getenv(
                "YBY_EMBED_MODEL",
                os.getenv("OLLAMA_MODEL_EMBEDDING", "all-minilm"),
            ),
            OLLAMA_MODEL_LLM=os.getenv("OLLAMA_MODEL_LLM", "llama3.2:3b"),
            FASTAPI_HOST=os.getenv("FASTAPI_HOST", "127.0.0.1"),
            FASTAPI_PORT=_env_int("FASTAPI_PORT", 8000),
            FASTAPI_WORKERS=_env_int("FASTAPI_WORKERS", 1),
            LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
            API_KEY=os.getenv("API_KEY") or None,
        )


settings = Settings.from_env()


def validate_settings() -> None:
    """Validar configurações obrigatórias."""
    required = ["MQTT_BROKER_HOST", "LANCEDB_PATH", "OLLAMA_HOST"]
    for field in required:
        if not getattr(settings, field):
            raise ValueError(f"Configuração obrigatória: {field}")


if __name__ == "__main__":
    validate_settings()
    print("✅ Configurações validadas")
