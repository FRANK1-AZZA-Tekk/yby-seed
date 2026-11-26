"""Barramento MQTT assíncrono (QoS 1) para estado de áudio e comandos do T-Watch."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class PublishedMessage:
    topic: str
    payload: str
    qos: int = 1
    retain: bool = False


@runtime_checkable
class MqttPublisher(Protocol):
    async def publish(
        self,
        topic: str,
        payload: str,
        *,
        qos: int = 1,
        retain: bool = False,
    ) -> None: ...


class InMemoryMqttBus:
    """Barramento MQTT em memória para testes 100% offline."""

    def __init__(self) -> None:
        self.messages: list[PublishedMessage] = []

    async def publish(
        self,
        topic: str,
        payload: str,
        *,
        qos: int = 1,
        retain: bool = False,
    ) -> None:
        self.messages.append(
            PublishedMessage(topic=topic, payload=payload, qos=qos, retain=retain)
        )


class PahoMqttPublisher:
    """Publica mensagens QoS 1 no Mosquitto usando `asyncio.to_thread` (não bloqueante)."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 1883,
        client_id: str = "yby-audio-bus",
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
        ca_certs: str | None = None,
        tls_insecure: bool = False,
        client: Any = None,
    ) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self.username = username
        self.password = password
        self.use_tls = use_tls or (port == 8883)
        self.ca_certs = ca_certs
        self.tls_insecure = tls_insecure
        self._client = client
        self._connected = False

    def _ensure_connected(self) -> Any:
        if self._client is None:
            import paho.mqtt.client as mqtt

            if hasattr(mqtt, "CallbackAPIVersion"):
                self._client = mqtt.Client(
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                    client_id=self.client_id,
                )
            else:
                self._client = mqtt.Client(client_id=self.client_id)
            if self.username:
                self._client.username_pw_set(self.username, self.password)
            if self.use_tls:
                tls_kwargs: dict[str, Any] = {}
                if self.ca_certs:
                    tls_kwargs["ca_certs"] = self.ca_certs
                self._client.tls_set(**tls_kwargs)
                if self.tls_insecure:
                    self._client.tls_insecure_set(True)
        if not self._connected:
            self._client.connect(self.host, self.port, keepalive=60)
            self._client.loop_start()
            self._connected = True
        return self._client

    def _publish_sync(self, topic: str, payload: str, qos: int, retain: bool) -> None:
        client = self._ensure_connected()
        info = client.publish(topic, payload=payload, qos=qos, retain=retain)
        if hasattr(info, "wait_for_publish"):
            info.wait_for_publish(timeout=5.0)

    async def publish(
        self,
        topic: str,
        payload: str,
        *,
        qos: int = 1,
        retain: bool = False,
    ) -> None:
        await asyncio.to_thread(self._publish_sync, topic, payload, qos, retain)

    def close(self) -> None:
        if self._client is not None and self._connected:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
