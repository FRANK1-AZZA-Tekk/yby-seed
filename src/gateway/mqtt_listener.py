"""
MQTT Listener — Subscriber assíncrono com auto-reconnect

Responsabilidade:
- Assinar tópicos MQTT (yby/#)
- Enfileirar mensagens para processamento (backpressure)
- Auto-reconnect com backoff exponencial
- Last Will Testament (LWT) para detectar desconexões

Arquitetura:
[MQTT Broker] → [paho.mqtt.client] → [on_message callback] → [asyncio.Queue]

Backoff exponencial:
- reconnect_timeout_ms=1000 (inicial)
- reconnect_timeout_ms *= 2 (após cada falha)
- reconnect_timeout_ms_max=60000 (máximo 60s)

Licença: MIT
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

import paho.mqtt.client as mqtt

from .config import settings

logger = logging.getLogger(__name__)


def _configure_mqtt_security(client: Any) -> None:
    if settings.MQTT_USERNAME:
        client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD or "")
    if settings.MQTT_USE_TLS:
        tls_kwargs: dict[str, Any] = {}
        if settings.MQTT_CA_CERTS:
            tls_kwargs["ca_certs"] = settings.MQTT_CA_CERTS
        if settings.MQTT_CERTFILE:
            tls_kwargs["certfile"] = settings.MQTT_CERTFILE
        if settings.MQTT_KEYFILE:
            tls_kwargs["keyfile"] = settings.MQTT_KEYFILE
        client.tls_set(**tls_kwargs)
        if settings.MQTT_TLS_INSECURE:
            client.tls_insecure_set(True)


async def mqtt_listener(queue: asyncio.Queue[Any]) -> None:
    """
    Subscriber MQTT assíncrono com ciclo de vida completo (encerra loop no cancelamento).

    Args:
        queue: asyncio.Queue para enfileirar mensagens (backpressure)
    """
    logger.info("📡 Iniciando MQTT listener...")

    loop = asyncio.get_running_loop()
    client_kwargs: dict[str, Any] = {
        "client_id": settings.MQTT_CLIENT_ID,
        "clean_session": False,  # Manter sessão para QoS 2
        "userdata": {"queue": queue, "loop": loop},
    }
    if hasattr(mqtt, "CallbackAPIVersion"):
        client_kwargs["callback_api_version"] = mqtt.CallbackAPIVersion.VERSION1
    client = mqtt.Client(**client_kwargs)

    # Callbacks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.on_subscribe = on_subscribe

    _configure_mqtt_security(client)

    # Auto-reconnect com backoff exponencial (assinatura paho: min_delay, max_delay)
    client.reconnect_delay_set(
        min_delay=1,
        max_delay=60,
    )

    # Last Will Testament (LWT)
    client.will_set(
        topic="yby/status",
        payload=f"{settings.MQTT_CLIENT_ID} offline",
        qos=1,
        retain=True,
    )

    # Conectar e manter ativo até cancelamento do lifespan
    started = False
    try:
        client.connect(
            host=settings.MQTT_BROKER_HOST,
            port=settings.MQTT_BROKER_PORT,
            keepalive=60,
        )
        client.loop_start()
        started = True
        logger.info("✅ MQTT listener conectado")
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("🛑 Encerrando MQTT listener...")
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao conectar MQTT: {e}")
        raise
    finally:
        if started:
            try:
                client.loop_stop()
            finally:
                client.disconnect()


def on_connect(client, userdata, flags, rc):
    """Callback: conexão estabelecida"""
    if rc == 0:
        logger.info("✅ MQTT conectado com sucesso")
        
        # Assinar tópicos
        client.subscribe("yby/#", qos=1)
        logger.info("📥 Assinando tópicos: yby/#")
        
        # Publicar status online
        client.publish(
            topic="yby/status",
            payload=f"{settings.MQTT_CLIENT_ID} online",
            qos=1,
            retain=True
        )
    
    else:
        logger.error(f"❌ Falha ao conectar MQTT: rc={rc}")


def on_disconnect(client, userdata, rc):
    """Callback: desconexão detectada"""
    if rc != 0:
        logger.warning(f"⚠️  MQTT desconectado inesperadamente: rc={rc}")
        # Auto-reconnect será acionado automaticamente


def on_subscribe(client, userdata, mid, granted_qos):
    """Callback: subscrição confirmada"""
    logger.info(f"✅ Subscrição confirmada: mid={mid}, qos={granted_qos}")


def enqueue_mqtt_payload(
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue[Any],
    data: dict[str, Any],
    *,
    on_dropped: Callable[[], None] | None = None,
) -> None:
    """
    Agenda ``put_nowait`` no loop asyncio (seguro a partir da thread do Paho).
    """

    def _put() -> None:
        try:
            queue.put_nowait(data)
        except asyncio.QueueFull:
            if on_dropped is not None:
                on_dropped()
            else:
                logger.warning("iot_mqtt_gateway_queue_drop", extra={"queue_size": queue.qsize()})

    if loop.is_closed():
        logger.debug("iot_mqtt_gateway_loop_closed")
        return
    try:
        loop.call_soon_threadsafe(_put)
    except RuntimeError:
        logger.debug("iot_mqtt_gateway_loop_closed")


def on_message(client, userdata, msg) -> None:
    """
    Callback: mensagem recebida (thread do Paho).

    Enfileira via ``call_soon_threadsafe`` para o ``asyncio.Queue`` do worker.
    """
    del client
    queue: asyncio.Queue[Any] = userdata["queue"]
    loop: asyncio.AbstractEventLoop = userdata["loop"]

    try:
        data = json.loads(msg.payload.decode("utf-8"))
        if not isinstance(data, dict):
            logger.warning("iot_mqtt_gateway_invalid_payload_type")
            return
        data["_metadata"] = {
            "topic": msg.topic,
            "qos": msg.qos,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        enqueue_mqtt_payload(loop, queue, data)
        logger.debug("iot_mqtt_gateway_enqueued", extra={"topic": msg.topic})
    except Exception as e:
        logger.error("iot_mqtt_gateway_parse_error", extra={"error_type": type(e).__name__})
