"""Cliente MQTT para sensores locais (paho-mqtt, sem nuvem por padrão)."""

from __future__ import annotations

import logging
from typing import Any, Callable

from src.iot.config import IoTConfig

logger = logging.getLogger(__name__)

MessageCallback = Callable[[str, bytes], None]


def _create_paho_client(config: IoTConfig, client_id: str) -> Any:
    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:
        raise ImportError("Instale requirements-iot.txt (paho-mqtt).") from exc

    client = mqtt.Client(client_id=client_id)
    if config.username:
        client.username_pw_set(config.username, config.password or "")
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    return client


class MQTTClient:
    """
    Conexão ao broker MQTT do PC Hub.

    Suporta auth por usuário/senha e reconexão automática (``loop_start``).
    Injete ``mqtt_client`` nos testes.
    """

    def __init__(
        self,
        config: IoTConfig,
        *,
        client_id: str = "yby-iot",
        mqtt_client: Any | None = None,
        autoconnect: bool = True,
    ) -> None:
        self._config = config
        self._message_callback: MessageCallback | None = None
        self._client = mqtt_client if mqtt_client is not None else _create_paho_client(config, client_id)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
        if autoconnect and mqtt_client is None:
            self.connect()

    @property
    def config(self) -> IoTConfig:
        return self._config

    @property
    def underlying(self) -> Any:
        return self._client

    def connect(self) -> None:
        """Conecta ao broker e inicia loop em thread para reconexão."""
        self._client.connect(self._config.broker_host, self._config.broker_port, keepalive=60)
        self._client.loop_start()

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def subscribe(self, topics: list[str] | None = None) -> None:
        """Inscreve nos tópicos (padrão: ``config.topics``)."""
        target = topics if topics is not None else self._config.topics
        for topic in target:
            self._client.subscribe(topic)

    def on_message(self, callback: MessageCallback) -> None:
        """Registra callback ``(topic, payload_bytes)``."""
        self._message_callback = callback

    def publish(self, topic: str, payload: str | bytes) -> None:
        """Publica mensagem no broker."""
        body = payload.encode("utf-8") if isinstance(payload, str) else payload
        self._client.publish(topic, body)

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int) -> None:
        del client, userdata, flags
        if rc != 0:
            logger.warning("MQTT connect rc=%s", rc)
            return
        for topic in self._config.topics:
            self._client.subscribe(topic)

    def _on_disconnect(self, client: Any, userdata: Any, rc: int) -> None:
        del client, userdata
        if rc != 0:
            logger.info("MQTT desconectado (rc=%s); paho tentará reconectar.", rc)

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        del client, userdata
        if self._message_callback is not None:
            self._message_callback(message.topic, message.payload)