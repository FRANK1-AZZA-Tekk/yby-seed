"""Barramento MQTT assíncrono (QoS 1) para estado de áudio e comandos do T-Watch."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from src.yby.audio.schemas import TOPIC_TWATCH_TELEMETRY, TOPIC_TWATCH_VOICE

logger = logging.getLogger("yby.audio.mqtt_bus")


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
        client: Any = None,
    ) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self.username = username
        self.password = password
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


class PahoMqttBridgeSubscriber:
    """Assina tópicos do T-Watch no Mosquitto e encaminha eventos para o hub."""

    def __init__(
        self,
        *,
        handler: Callable[[str, bytes | str], Awaitable[Any] | Any],
        host: str = "127.0.0.1",
        port: int = 1883,
        topics: Sequence[str] = (TOPIC_TWATCH_VOICE, TOPIC_TWATCH_TELEMETRY),
        client_id: str = "yby-twatch-subscriber",
        username: str | None = None,
        password: str | None = None,
        client: Any = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self.handler = handler
        self.host = host
        self.port = port
        self.topics = tuple(topics)
        self.client_id = client_id
        self.username = username
        self.password = password
        self._client = client
        self._loop = loop
        self._connected = False

    def _build_client(self) -> Any:
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

        def _on_connect(client: Any, *_args: Any) -> None:
            for topic in self.topics:
                client.subscribe(topic, qos=1)

        def _on_message(_client: Any, _userdata: Any, msg: Any) -> None:
            topic = str(getattr(msg, "topic", ""))
            payload = getattr(msg, "payload", b"")
            try:
                self.process_message(topic, payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Erro ao despachar mensagem MQTT de %s: %s", topic, exc)

        self._client.on_connect = _on_connect
        self._client.on_message = _on_message
        return self._client

    def process_message(self, topic: str, payload: bytes | str) -> Any:
        """Processa uma mensagem recebida e agenda corrotinas no event loop configurado."""

        result = self.handler(topic, payload)
        if not inspect.isawaitable(result):
            return result

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        if running is not None:
            return running.create_task(result)

        if self._loop is not None and self._loop.is_running():
            return asyncio.run_coroutine_threadsafe(result, self._loop)

        return asyncio.run(result)

    def start(self, *, loop: asyncio.AbstractEventLoop | None = None) -> None:
        if loop is not None:
            self._loop = loop
        elif self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = None

        client = self._build_client()
        if not self._connected:
            client.connect(self.host, self.port, keepalive=60)
            client.loop_start()
            self._connected = True

    def stop(self) -> None:
        if self._client is not None and self._connected:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
