"""Configuração do broker MQTT local (PC Hub, D9)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_BROKER_HOST = "localhost"
DEFAULT_BROKER_PORT = 1883
DEFAULT_TOPICS: tuple[str, ...] = ("yby/sensors/#",)
DEFAULT_RECONNECT_MAX_ATTEMPTS = 5
DEFAULT_RECONNECT_BASE_SECONDS = 1.0
DEFAULT_MAX_QUEUE_SIZE = 100


def _text(source: Mapping[str, str], name: str, default: str) -> str:
    raw = source.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip()


def _int(source: Mapping[str, str], name: str, default: int) -> int:
    raw = source.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    port = int(str(raw).strip())
    if port < 1 or port > 65535:
        raise ValueError(f"{name} deve estar entre 1 e 65535.")
    return port


def _topics(source: Mapping[str, str], name: str) -> list[str]:
    raw = source.get(name)
    if raw is None or str(raw).strip() == "":
        return list(DEFAULT_TOPICS)
    parts = [part.strip() for part in str(raw).split(",") if part.strip()]
    if not parts:
        return list(DEFAULT_TOPICS)
    return parts


@dataclass(frozen=True)
class IoTConfig:
    """Parâmetros de conexão MQTT. Credenciais só via ambiente."""

    broker_host: str
    broker_port: int
    username: str | None
    password: str | None
    topics: list[str]
    reconnect_max_attempts: int
    reconnect_base_seconds: float
    max_queue_size: int

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> IoTConfig:
        if environ is None:
            load_dotenv(override=False)
            source: Mapping[str, str] = os.environ
        else:
            source = environ

        user = _text(source, "IOT_USERNAME", "")
        password = _text(source, "IOT_PASSWORD", "")
        max_att = _int(source, "IOT_RECONNECT_MAX_ATTEMPTS", DEFAULT_RECONNECT_MAX_ATTEMPTS)
        if max_att < 1:
            raise ValueError("IOT_RECONNECT_MAX_ATTEMPTS deve ser >= 1.")
        queue_size = _int(source, "IOT_MAX_QUEUE_SIZE", DEFAULT_MAX_QUEUE_SIZE)
        if queue_size < 1:
            raise ValueError("IOT_MAX_QUEUE_SIZE deve ser >= 1.")
        base_raw = _text(source, "IOT_RECONNECT_BASE_SECONDS", str(DEFAULT_RECONNECT_BASE_SECONDS))
        base_sec = float(base_raw)
        if base_sec <= 0:
            raise ValueError("IOT_RECONNECT_BASE_SECONDS deve ser > 0.")

        return cls(
            broker_host=_text(source, "IOT_BROKER_HOST", DEFAULT_BROKER_HOST),
            broker_port=_int(source, "IOT_BROKER_PORT", DEFAULT_BROKER_PORT),
            username=user or None,
            password=password if user and password else None,
            topics=_topics(source, "IOT_TOPICS"),
            reconnect_max_attempts=max_att,
            reconnect_base_seconds=base_sec,
            max_queue_size=queue_size,
        )