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
import paho.mqtt.client as mqtt
import logging
from datetime import datetime
from typing import Queue

from .config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def mqtt_listener(queue: Queue):
    """
    Subscriber MQTT assíncrono.
    
    Args:
        queue: asyncio.Queue para enfileirar mensagens (backpressure)
    """
    logger.info("📡 Iniciando MQTT listener...")
    
    # Configurar cliente MQTT
    client = mqtt.Client(
        client_id=settings.MQTT_CLIENT_ID,
        clean_session=False,  # Manter sessão para QoS 2
        userdata={"queue": queue}
    )
    
    # Callbacks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.on_subscribe = on_subscribe
    
    # Auto-reconnect com backoff exponencial
    client.reconnect_delay_set(
        min_delay=1,    # 1 segundo inicial
        max_delay=60,   # 60 segundos máximo
        exponential_base=2
    )
    
    # Last Will Testament (LWT)
    client.will_set(
        topic="yby/status",
        payload=f"{settings.MQTT_CLIENT_ID} offline",
        qos=1,
        retain=True
    )
    
    # Conectar
    try:
        client.connect(
            host=settings.MQTT_BROKER_HOST,
            port=settings.MQTT_BROKER_PORT,
            keepalive=60  # Ping a cada 60s
        )
        client.loop_start()  # Thread background para MQTT
        logger.info("✅ MQTT listener conectado")
    
    except Exception as e:
        logger.error(f"❌ Erro ao conectar MQTT: {e}")
        raise


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


def on_message(client, userdata, msg):
    """
    Callback: mensagem recebida.
    
    Enfileirar mensagem para processamento assíncrono (backpressure).
    """
    queue: Queue = userdata["queue"]
    
    try:
        # Parse payload JSON
        import json
        data = json.loads(msg.payload.decode("utf-8"))
        
        # Adicionar metadados
        data["_metadata"] = {
            "topic": msg.topic,
            "qos": msg.qos,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Enfileirar (non-blocking)
        try:
            queue.put_nowait(data)
            logger.debug(f"📨 Mensagem enfileirada: {msg.topic}")
        
        except asyncio.QueueFull:
            logger.warning("⚠️  Queue cheia, descartando mensagem")
    
    except Exception as e:
        logger.error(f"❌ Erro ao processar mensagem MQTT: {e}")
