"""
Termux API — Integração com sensores e notificações do Android

Responsabilidade:
- Ler sensores (bateria, GPS, notificações)
- Enviar notificações
- Executar comandos (SMS, clipboard, vibration)

Requisitos:
- Termux instalado
- Termux:API instalado (F-Droid ou Play Store)

Comandos:
- termux-battery-status
- termux-location
- termux-notification
- termux-sms-send
- termux-clipboard-set

Licença: MIT
"""

import subprocess
import json
import logging
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TermuxAPI:
    """
    Wrapper para Termux:API.
    """
    
    def __init__(self):
        # Verificar se Termux:API está instalado
        self.api_installed = self._check_api_installed()
    
    def _check_api_installed(self) -> bool:
        """Verificar se Termux:API está instalado"""
        try:
            result = subprocess.run(
                ["pkg", "list-installed", "termux-api"],
                capture_output=True,
                text=True
            )
            return "termux-api" in result.stdout
        
        except Exception:
            return False
    
    def get_battery_status(self) -> Dict[str, Any]:
        """
        Obter status da bateria.
        
        Returns:
            Dict com status (percent, health, status, temperature)
        """
        logger.info("🔋 Lendo bateria...")
        
        try:
            result = subprocess.run(
                ["termux-battery-status"],
                capture_output=True,
                text=True,
                check=True
            )
            
            data = json.loads(result.stdout)
            
            return {
                "percent": data.get("percentage", 0),
                "health": data.get("health", "UNKNOWN"),
                "status": data.get("status", "UNKNOWN"),
                "temperature": data.get("temperature", 0.0),
                "voltage": data.get("voltage", 0)
            }
        
        except Exception as e:
            logger.error(f"❌ Erro ao ler bateria: {e}")
            return {}
    
    def get_location(self) -> Dict[str, Any]:
        """
        Obter localização GPS.
        
        Returns:
            Dict com localização (lat, lon, altitude, accuracy)
        """
        logger.info("📍 Lendo GPS...")
        
        try:
            result = subprocess.run(
                ["termux-location"],
                capture_output=True,
                text=True,
                check=True
            )
            
            data = json.loads(result.stdout)
            
            return {
                "lat": data.get("latitude", 0.0),
                "lon": data.get("longitude", 0.0),
                "altitude": data.get("altitude", 0.0),
                "accuracy": data.get("accuracy", 0.0),
                "provider": data.get("provider", "unknown")
            }
        
        except Exception as e:
            logger.error(f"❌ Erro ao ler GPS: {e}")
            return {}
    
    def send_notification(self, title: str, content: str, channel: str = "yby"):
        """
        Enviar notificação.
        
        Args:
            title: Título da notificação
            content: Conteúdo da notificação
            channel: Canal da notificação
        """
        logger.info(f"🔔 Enviando notificação: {title}")
        
        try:
            subprocess.run(
                [
                    "termux-notification",
                    "--title", title,
                    "--content", content,
                    "--channel", channel
                ],
                check=True
            )
            logger.info("✅ Notificação enviada")
        
        except Exception as e:
            logger.error(f"❌ Erro ao enviar notificação: {e}")
    
    def send_sms(self, phone_number: str, message: str):
        """
        Enviar SMS.
        
        Args:
            phone_number: Número de telefone
            message: Mensagem
        """
        logger.info(f"📱 Enviando SMS para {phone_number}...")
        
        try:
            subprocess.run(
                [
                    "termux-sms-send",
                    "-n", phone_number,
                    message
                ],
                check=True
            )
            logger.info("✅ SMS enviado")
        
        except Exception as e:
            logger.error(f"❌ Erro ao enviar SMS: {e}")
    
    def set_clipboard(self, text: str):
        """
        Definir clipboard.
        
        Args:
            text: Texto para copiar
        """
        logger.info(f"📋 Copiando para clipboard: {text[:50]}...")
        
        try:
            subprocess.run(
                ["termux-clipboard-set", text],
                check=True
            )
            logger.info("✅ Clipboard definido")
        
        except Exception as e:
            logger.error(f"❌ Erro ao definir clipboard: {e}")
    
    def get_clipboard(self) -> str:
        """
        Obter clipboard.
        
        Returns:
            Texto do clipboard
        """
        logger.info("📋 Lendo clipboard...")
        
        try:
            result = subprocess.run(
                ["termux-clipboard-get"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        
        except Exception as e:
            logger.error(f"❌ Erro ao ler clipboard: {e}")
            return ""
    
    def vibrate(self, duration_ms: int = 1000):
        """
        Vibrar dispositivo.
        
        Args:
            duration_ms: Duração em milissegundos
        """
        logger.info(f"📳 Vibrando por {duration_ms}ms...")
        
        try:
            subprocess.run(
                ["termux-vibrate", "-d", str(duration_ms)],
                check=True
            )
            logger.info("✅ Vibração executada")
        
        except Exception as e:
            logger.error(f"❌ Erro ao vibrar: {e}")
    
    def get_sensors(self) -> Dict[str, Any]:
        """
        Obter dados de sensores (acelerômetro, giroscópio, etc.).
        
        Returns:
            Dict com dados de sensores
        """
        logger.info("📊 Lendo sensores...")
        
        # TODO: Implementar com termux-sensor
        return {
            "accelerometer": {"x": 0, "y": 0, "z": 0},
            "gyroscope": {"x": 0, "y": 0, "z": 0},
            "magnetometer": {"x": 0, "y": 0, "z": 0}
        }


# Instância global
termux_api = TermuxAPI()


if __name__ == "__main__":
    # Verificar API
    if not termux_api.api_installed:
        print("❌ Termux:API não instalado. Execute: pkg install termux-api")
    
    # Bateria
    battery = termux_api.get_battery_status()
    print(f"\n🔋 Bateria: {battery}")
    
    # GPS
    location = termux_api.get_location()
    print(f"\n📍 GPS: {location}")
    
    # Notificação
    termux_api.send_notification("YBY SEED", "Teste de notificação")
    
    # Clipboard
    termux_api.set_clipboard("Texto copiado")
    text = termux_api.get_clipboard()
    print(f"\n📋 Clipboard: {text}")
    
    # Vibração
    termux_api.vibrate(500)
