"""
Mobile Gateway — Gateway MQTT no Termux (Xiaomi 12)

Responsabilidade:
- Publicar telemetria no broker MQTT
- Assinar comandos do gateway (FastAPI)
- Executar ações locais (notificações, SMS, automações)

Arquitetura:
[ESP32-S3] → [MQTT Broker] ← [Termux Gateway] → [Termux:API]

Tópicos MQTT:
- yby/telemetry: Telemetria do wearable
- yby/commands: Comandos para o gateway
- yby/status: Status do gateway

Licença: MIT
"""

import paho.mqtt.client as mqtt
import json
import logging
from datetime import datetime
from typing import Dict, Any

from .termux_api import termux_api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MobileGateway:
    """
    Gateway MQTT no Termux.
    """
    
    def __init__(self, broker_host: str = "broker.yby.local", broker_port: int = 1883):
        """
        Inicializar gateway.
        
        Args:
            broker_host: Host do broker MQTT
            broker_port: Porta do broker
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        
        # Cliente MQTT
        self.client = mqtt.Client(
            client_id="yby-mobile-gateway",
            clean_session=False
        )
        
        # Callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
    
    def connect(self):
        """Conectar ao broker MQTT"""
        logger.info(f"📡 Conectando MQTT: {self.broker_host}:{self.broker_port}...")
        
        try:
            self.client.connect(
                host=self.broker_host,
                port=self.broker_port,
                keepalive=60
            )
            self.client.loop_start()
            logger.info("✅ MQTT conectado")
        
        except Exception as e:
            logger.error(f"❌ Erro ao conectar MQTT: {e}")
            raise
    
    def disconnect(self):
        """Desconectar do broker"""
        logger.info("📡 Desconectando MQTT...")
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("✅ MQTT desconectado")
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback: conexão estabelecida"""
        if rc == 0:
            logger.info("✅ MQTT conectado com sucesso")
            
            # Assinar tópicos de comandos
            self.client.subscribe("yby/commands", qos=1)
            logger.info("📥 Assinando tópicos: yby/commands")
            
            # Publicar status online
            self.client.publish(
                topic="yby/status",
                payload="yby-mobile-gateway online",
                qos=1,
                retain=True
            )
        
        else:
            logger.error(f"❌ Falha ao conectar MQTT: rc={rc}")
    
    def on_disconnect(self, client, userdata, rc):
        """Callback: desconexão detectada"""
        if rc != 0:
            logger.warning(f"⚠️  MQTT desconectado inesperadamente: rc={rc}")
    
    def on_message(self, client, userdata, msg):
        """
        Callback: mensagem recebida.
        
        Processar comandos:
        - send_notification
        - send_sms
        - vibrate
        - set_clipboard
        """
        logger.info(f"📨 MQTT mensagem recebida: {msg.topic}")
        
        try:
            # Parse payload JSON
            data = json.loads(msg.payload.decode("utf-8"))
            
            # Processar comando
            action = data.get("action")
            
            if action == "send_notification":
                termux_api.send_notification(
                    title=data.get("title", "YBY SEED"),
                    content=data.get("content", ""),
                    channel=data.get("channel", "yby")
                )
            
            elif action == "send_sms":
                termux_api.send_sms(
                    phone_number=data.get("phone_number"),
                    message=data.get("message")
                )
            
            elif action == "vibrate":
                termux_api.vibrate(duration_ms=data.get("duration_ms", 1000))
            
            elif action == "set_clipboard":
                termux_api.set_clipboard(text=data.get("text"))
            
            else:
                logger.warning(f"⚠️  Ação desconhecida: {action}")
        
        except Exception as e:
            logger.error(f"❌ Erro ao processar comando: {e}")
    
    def publish_telemetry(self, telemetry: Dict[str, Any]):
        """
        Publicar telemetria.
        
        Args:
            telemetry: Dados de telemetria
        """
        logger.info("📤 Publicando telemetria...")
        
        # Adicionar timestamp
        telemetry["timestamp"] = datetime.utcnow().isoformat()
        
        # Publicar
        payload = json.dumps(telemetry)
        
        self.client.publish(
            topic="yby/telemetry",
            payload=payload,
            qos=1
        )
        
        logger.info("✅ Telemetria publicada")


# Instância global
mobile_gateway = MobileGateway()


if __name__ == "__main__":
    # Conectar
    mobile_gateway.connect()
    
    # Publicar telemetria
    telemetry = {
        "device_id": "xiaomi-12",
        "metrics": {
            "battery": 85,
            "temperature": 35.2,
            "location": {"lat": -23.5505, "lon": -46.6333}
        }
    }
    
    mobile_gateway.publish_telemetry(telemetry)
    
    # Aguardar comandos
    import time
    
    try:
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        mobile_gateway.disconnect()
