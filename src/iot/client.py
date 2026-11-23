"""Cliente MQTT para sensores locais (paho-mqtt, sem nuvem por padrão)."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from src.iot.config import IoTConfig
from src.iot.message_queue import BoundedMessageQueue
from src.iot.reconnect import next_reconnect_delay

logger = logging.getLogger(__name__)

MessageCallback = Callable[[str, bytes], None]
ReconnectScheduler = Callable[[float, Callable[[], None]], None]


def _default_scheduler(delay: float, run: Callable[[], None]) -> None:
    timer = threading.Timer(delay, run)
    timer.daemon = True
    timer.start()


def _create_paho_client(config: IoTConfig, client_id: str) -> Any:
    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:
        raise ImportError("Instale requirements-iot.txt (paho-mqtt).") from exc

    client = mqtt.Client(client_id=client_id)
    if config.username:
        client.username_pw_set(config.username, config.password or "")
    # Reconexão manual com backoff; desativa backoff automático do paho.
    client.reconnect_delay_set(min_delay=0, max_delay=0)
    return client


class MQTTClient:
    """
    Conexão ao broker MQTT do PC Hub.

    Suporta auth por usuário/senha, fila limitada e reconexão com backoff + jitter.
    Injete ``mqtt_client`` nos testes.
    """

    def __init__(
        self,
        config: IoTConfig,
        *,
        client_id: str = "yby-iot",
        mqtt_client: Any | None = None,
        autoconnect: bool = True,
        message_queue: BoundedMessageQueue | None = None,
        schedule_reconnect: ReconnectScheduler | None = None,
    ) -> None:
        self._config = config
        self._message_callback: MessageCallback | None = None
        self._queue = (
            message_queue
            if message_queue is not None
            else BoundedMessageQueue(max_size=config.max_queue_size)
        )
        self._schedule = schedule_reconnect or _default_scheduler
        self._reconnect_attempt = 0
        self._reconnect_lock = threading.Lock()
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

    @property
    def message_queue(self) -> BoundedMessageQueue:
        return self._queue

    @property
    def reconnect_attempts(self) -> int:
        return self._reconnect_attempt

    def connect(self) -> None:
        """Conecta ao broker e inicia loop em thread."""
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

    def _schedule_reconnect(self) -> None:
        with self._reconnect_lock:
            if self._reconnect_attempt >= self._config.reconnect_max_attempts:
                logger.warning(
                    "iot_mqtt_reconnect_exhausted",
                    extra={
                        "attempts": self._reconnect_attempt,
                        "max_attempts": self._config.reconnect_max_attempts,
                    },
                )
                return
            delay = next_reconnect_delay(
                self._reconnect_attempt,
                base_seconds=self._config.reconnect_base_seconds,
            )
            attempt_no = self._reconnect_attempt
            self._reconnect_attempt += 1
        logger.info(
            "iot_mqtt_reconnect_scheduled",
            extra={"attempt": attempt_no + 1, "delay_seconds": round(delay, 3)},
        )
        self._schedule(delay, self._try_reconnect)

    def _try_reconnect(self) -> None:
        try:
            self._client.reconnect()
        except Exception:
            logger.exception("iot_mqtt_reconnect_failed")
            self._schedule_reconnect()

    def _drain_queue(self) -> None:
        if self._message_callback is None:
            return
        while True:
            item = self._queue.pop()
            if item is None:
                break
            topic, payload = item
            self._message_callback(topic, payload)

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int) -> None:
        del client, userdata, flags
        if rc != 0:
            logger.warning("iot_mqtt_connect_rejected", extra={"rc": rc})
            return
        self._reconnect_attempt = 0
        for topic in self._config.topics:
            self._client.subscribe(topic)

    def _on_disconnect(self, client: Any, userdata: Any, rc: int) -> None:
        del client, userdata
        if rc == 0:
            return
        logger.info("iot_mqtt_disconnected", extra={"rc": rc})
        self._schedule_reconnect()

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        del client, userdata
        payload = message.payload
        if not isinstance(payload, bytes):
            payload = bytes(payload)
        if not self._queue.offer(message.topic, payload):
            return
        self._drain_queue()