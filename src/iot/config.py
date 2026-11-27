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
    try:
        return int(str(raw).strip())
    except ValueError as exc:
        raise ValueError(f"{name} deve ser um inteiro válido.") from exc


def _port(source: Mapping[str, str], name: str, default: int) -> int:
    port = _int(source, name, default)
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


def _bool(source: Mapping[str, str], name: str, default: bool) -> bool:
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
    use_tls: bool = False
    ca_certs: str | None = None
    certfile: str | None = None
    keyfile: str | None = None
    tls_insecure: bool = False
    require_tls: bool = False

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

        port = _port(source, "IOT_BROKER_PORT", DEFAULT_BROKER_PORT)
        use_tls = _bool(source, "IOT_USE_TLS", default=(port == 8883))
        ca_certs = _text(source, "IOT_CA_CERTS", "") or None
        certfile = _text(source, "IOT_CERTFILE", "") or None
        keyfile = _text(source, "IOT_KEYFILE", "") or None
        tls_insecure = _bool(source, "IOT_TLS_INSECURE", default=False)
        require_tls = _bool(source, "IOT_REQUIRE_TLS", default=False)

        if bool(certfile) != bool(keyfile):
            raise ValueError("IOT_CERTFILE e IOT_KEYFILE devem ser definidos em conjunto.")
        if require_tls and not use_tls:
            raise ValueError("IOT_REQUIRE_TLS=true exige TLS habilitado (IOT_USE_TLS=true ou porta 8883).")

        return cls(
            broker_host=_text(source, "IOT_BROKER_HOST", DEFAULT_BROKER_HOST),
            broker_port=port,
            username=user or None,
            password=password if user and password else None,
            topics=_topics(source, "IOT_TOPICS"),
            reconnect_max_attempts=max_att,
            reconnect_base_seconds=base_sec,
            max_queue_size=queue_size,
            use_tls=use_tls,
            ca_certs=ca_certs,
            certfile=certfile,
            keyfile=keyfile,
            tls_insecure=tls_insecure,
            require_tls=require_tls,
        )