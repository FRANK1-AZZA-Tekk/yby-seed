"""
Power Manager — Gerenciamento de energia (foreground service)

Responsabilidade:
- Manter Termux em execução (evitar kill em background)
- Otimizar consumo de bateria
- Monitorar temperatura e throttling

Requisitos:
- Xiaomi 12 (Android 15, HyperOS 3.0)
- Termux:Boot instalado
- Foreground service configurado

Estratégia:
- Foreground service (notificação persistente)
- Battery optimization whitelist
- CPU governor: performance (evitar throttling)

Licença: MIT
"""

import subprocess
import json
import logging
from typing import Dict, Any

from .termux_api import termux_api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PowerManager:
    """
    Gerenciamento de energia para Termux.
    """
    
    def __init__(self):
        # Estado
        self.foreground_service_active = False
        self.battery_optimization_disabled = False
    
    def enable_foreground_service(self):
        """
        Habilitar foreground service (notificação persistente).
        
        Evita que Android mate Termux em background.
        """
        logger.info("🔋 Habilitando foreground service...")
        
        # Criar script de boot (executa ao iniciar Termux)
        boot_script = """
#!/data/data/com.termux/files/usr/bin/bash

# Foreground service (notificação persistente)
termux-notification --title "YBY SEED Gateway" --content "Executando em background" --ongoing true

# Manter CPU ativa (evitar sleep)
while true; do
    sleep 300
done
"""
        
        # Salvar script
        with open("/data/data/com.termux/files/home/.termux/boot.sh", "w") as f:
            f.write(boot_script)
        
        # Tornar executável
        subprocess.run(["chmod", "+x", "/data/data/com.termux/files/home/.termux/boot.sh"])
        
        self.foreground_service_active = True
        logger.info("✅ Foreground service habilitado")
    
    def disable_battery_optimization(self):
        """
        Desabilitar battery optimization para Termux.
        
        Comando ADB:
        appops set com.termux IGNORE_BACKGROUND_RESTRICTIONS allow
        """
        logger.info("🔋 Desabilitando battery optimization...")
        
        try:
            # Via ADB (precisa de Shizuku ou root)
            subprocess.run(
                ["adb", "shell", "appops", "set", "com.termux", "IGNORE_BACKGROUND_RESTRICTIONS", "allow"],
                capture_output=True,
                text=True,
                check=True
            )
            
            self.battery_optimization_disabled = True
            logger.info("✅ Battery optimization desabilitado")
        
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Erro ao desabilitar battery optimization: {e.stderr}")
            logger.warning("⚠️  Execute manualmente via ADB:")
            logger.warning("adb shell appops set com.termux IGNORE_BACKGROUND_RESTRICTIONS allow")
    
    def set_cpu_governor(self, governor: str = "performance"):
        """
        Definir CPU governor.
        
        Governors:
        - performance: Máxima performance (mais consumo)
        - powersave: Economia de bateria (menos performance)
        - interactive: Balanceado (padrão)
        
        Args:
            governor: Governor (performance, powersave, interactive)
        """
        logger.info(f"🔋 Definindo CPU governor: {governor}...")
        
        # Nota: Requer root ou kernel com suporte
        try:
            # Listar governors disponíveis
            result = subprocess.run(
                ["cat", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors"],
                capture_output=True,
                text=True,
                check=True
            )
            
            available = result.stdout.strip().split()
            logger.info(f"📊 Governors disponíveis: {available}")
            
            # Definir governor
            if governor in available:
                subprocess.run(
                    ["echo", governor, ">", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"],
                    shell=True,
                    check=True
                )
                logger.info(f"✅ CPU governor definido: {governor}")
            
            else:
                logger.warning(f"⚠️  Governor não disponível: {governor}")
        
        except Exception as e:
            logger.error(f"❌ Erro ao definir CPU governor: {e}")
            logger.warning("⚠️  Requer root ou kernel com suporte")
    
    def get_power_stats(self) -> Dict[str, Any]:
        """
        Obter estatísticas de energia.
        
        Returns:
            Dict com stats (battery, temperature, cpu_freq)
        """
        logger.info("📊 Lendo estatísticas de energia...")
        
        # Bateria
        battery = termux_api.get_battery_status()
        
        # CPU frequency
        try:
            result = subprocess.run(
                ["cat", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"],
                capture_output=True,
                text=True,
                check=True
            )
            cpu_freq_mhz = int(result.stdout.strip()) // 1000
        
        except Exception:
            cpu_freq_mhz = 0
        
        return {
            "battery_percent": battery.get("percent", 0),
            "battery_temperature": battery.get("temperature", 0.0),
            "cpu_freq_mhz": cpu_freq_mhz,
            "foreground_service": self.foreground_service_active,
            "battery_optimization_disabled": self.battery_optimization_disabled
        }
    
    def monitor(self, interval_sec: int = 60):
        """
        Monitorar energia em tempo real.
        
        Args:
            interval_sec: Intervalo de leitura (segundos)
        """
        logger.info(f"📊 Monitorando energia (intervalo: {interval_sec}s)...")
        
        import time
        
        while True:
            stats = self.get_power_stats()
            
            logger.info(f"🔋 Bateria: {stats['battery_percent']}%, {stats['battery_temperature']}°C")
            logger.info(f"⚙️  CPU: {stats['cpu_freq_mhz']}MHz")
            
            # Alertas
            if stats["battery_percent"] < 20:
                logger.warning("⚠️  Bateria baixa (<20%)")
                termux_api.send_notification("YBY SEED", "Bateria baixa (<20%)")
            
            if stats["battery_temperature"] > 42:
                logger.warning("⚠️  Temperatura alta (>42°C)")
                termux_api.send_notification("YBY SEED", "Temperatura alta (>42°C)")
            
            time.sleep(interval_sec)


# Instância global
power_manager = PowerManager()


if __name__ == "__main__":
    # Habilitar foreground service
    power_manager.enable_foreground_service()
    
    # Desabilitar battery optimization
    power_manager.disable_battery_optimization()
    
    # Definir CPU governor
    power_manager.set_cpu_governor("performance")
    
    # Monitorar
    power_manager.monitor(interval_sec=30)
