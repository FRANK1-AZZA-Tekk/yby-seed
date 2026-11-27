"""Configuração do gateway. Host local e token vêm do ambiente."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


def _text(source: Mapping[str, str], name: str, default: str) -> str:
    value = source.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _number(source: Mapping[str, str], name: str, default: int) -> int:
    raw = source.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _flag(source: Mapping[str, str], name: str, default: bool) -> bool:
    raw = source.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    norm = str(raw).strip().casefold()
    if norm in {"1", "true", "yes", "on", "sim"}:
        return True
    if norm in {"0", "false", "no", "off", "nao", "não"}:
        return False
    raise ValueError(f"{name} deve ser booleano válido.")


@dataclass(frozen=True)
class Settings:
    """Configurações do gateway. Sem senha embutida."""

    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_CLIENT_ID: str = "yby-seed-gateway"
    MQTT_TOPIC_PREFIX: str = "yby"
    MQTT_USERNAME: str = ""
    MQTT_PASSWORD: str = ""
    MQTT_USE_TLS: bool = False
    MQTT_CA_CERTS: str | None = None
    MQTT_CERTFILE: str | None = None
    MQTT_KEYFILE: str | None = None
    MQTT_TLS_INSECURE: bool = False
    LANCEDB_PATH: str = "/data/vectors"
    LANCEDB_INDEX_CACHE_SIZE: int = 128
    OLLAMA_HOST: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL_EMBEDDING: str = "all-minilm:22m"
    OLLAMA_MODEL_LLM: str = "qwen2.5-coder:3b"
    FASTAPI_HOST: str = "127.0.0.1"
    FASTAPI_PORT: int = 8000
    FASTAPI_WORKERS: int = 1
    LOG_LEVEL: str = "INFO"
    GATEWAY_TOKEN: str = ""


def load_settings(source: Mapping[str, str] | None = None) -> Settings:
    """Lê o ambiente. `source` explícito não chama dotenv."""

    if source is None:
        from dotenv import load_dotenv

        load_dotenv(override=False)
        source = os.environ

    token = _text(source, "GATEWAY_TOKEN", "")
    if not token:
        token = _text(source, "API_KEY", "")

    mqtt_port = _number(source, "MQTT_BROKER_PORT", 1883)
    mqtt_use_tls = _flag(source, "MQTT_USE_TLS", default=(mqtt_port == 8883))
    mqtt_certfile = _text(source, "MQTT_CERTFILE", "") or None
    mqtt_keyfile = _text(source, "MQTT_KEYFILE", "") or None
    if bool(mqtt_certfile) != bool(mqtt_keyfile):
        raise ValueError("MQTT_CERTFILE e MQTT_KEYFILE devem ser definidos em conjunto.")

    return Settings(
        MQTT_BROKER_HOST=_text(source, "MQTT_BROKER_HOST", "localhost"),
        MQTT_BROKER_PORT=mqtt_port,
        MQTT_CLIENT_ID=_text(source, "MQTT_CLIENT_ID", "yby-seed-gateway"),
        MQTT_TOPIC_PREFIX=_text(source, "MQTT_TOPIC_PREFIX", "yby"),
        MQTT_USERNAME=_text(source, "MQTT_USERNAME", ""),
        MQTT_PASSWORD=_text(source, "MQTT_PASSWORD", ""),
        MQTT_USE_TLS=mqtt_use_tls,
        MQTT_CA_CERTS=_text(source, "MQTT_CA_CERTS", "") or None,
        MQTT_CERTFILE=mqtt_certfile,
        MQTT_KEYFILE=mqtt_keyfile,
        MQTT_TLS_INSECURE=_flag(source, "MQTT_TLS_INSECURE", default=False),
        LANCEDB_PATH=_text(source, "LANCEDB_PATH", "/data/vectors"),
        LANCEDB_INDEX_CACHE_SIZE=_number(source, "LANCEDB_INDEX_CACHE_SIZE", 128),
        OLLAMA_HOST=_text(source, "OLLAMA_HOST", "http://127.0.0.1:11434"),
        OLLAMA_MODEL_EMBEDDING=_text(source, "OLLAMA_MODEL_EMBEDDING", "all-minilm:22m"),
        OLLAMA_MODEL_LLM=_text(source, "OLLAMA_MODEL_LLM", "qwen2.5-coder:3b"),
        FASTAPI_HOST=_text(source, "FASTAPI_HOST", "127.0.0.1"),
        FASTAPI_PORT=_number(source, "FASTAPI_PORT", 8000),
        FASTAPI_WORKERS=_number(source, "FASTAPI_WORKERS", 1),
        LOG_LEVEL=_text(source, "LOG_LEVEL", "INFO"),
        GATEWAY_TOKEN=token,
    )


settings = load_settings()


def validate_settings() -> None:
    """Confere o mínimo para subir o processo."""

    required = ["MQTT_BROKER_HOST", "LANCEDB_PATH", "OLLAMA_HOST"]
    for field in required:
        if not getattr(settings, field):
            raise ValueError(f"Configuração obrigatória: {field}")
