"""
ADB Injector — Injeção de comandos ADB via Shizuku (sem root)

Responsabilidade:
- Desativar Phantom Process Killer (PPK)
- Desativar MiuiSentinelMemoryManager
- Prevenir sobrescrita de configurações

Requisitos:
- Xiaomi 12 (Android 15, HyperOS 3.0)
- Shizuku instalado (Play Store)
- ADB wireless ativado

Comandos ADB:
- device_config put activity_manager max_phantom_processes 2147483647
- settings put global settings_enable_monitor_phantom_procs false
- appops set com.miui.powerkeeper GET_USAGE_STATS deny

Licença: MIT
"""

import subprocess
import logging
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ADBInjector:
    """
    Injeção de comandos ADB via Shizuku (sem root).
    """
    
    def __init__(self, device_id: str = None):
        """
        Inicializar injector.
        
        Args:
            device_id: ID do dispositivo (ex: "xiaomi_12")
        """
        self.device_id = device_id
        self.adb_path = self._find_adb()
    
    def _find_adb(self) -> str:
        """Encontrar ADB no sistema"""
        paths = [
            "/usr/bin/adb",
            "/usr/local/bin/adb",
            "C:\\Platform-tools\\adb.exe",
            "adb"
        ]
        
        for path in paths:
            try:
                subprocess.run([path, "version"], capture_output=True, check=True)
                return path
            except Exception:
                continue
        
        raise FileNotFoundError("ADB não encontrado. Instale Android Platform Tools.")
    
    def connect_wireless(self, ip: str, port: int = 5555):
        """
        Conectar via ADB wireless.
        
        Args:
            ip: IP do dispositivo
            port: Porta ADB (padrão: 5555)
        """
        logger.info(f"📱 Conectando ADB wireless: {ip}:{port}...")
        
        try:
            subprocess.run(
                [self.adb_path, "connect", f"{ip}:{port}"],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"✅ ADB wireless conectado: {ip}:{port}")
        
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Erro ao conectar: {e.stderr}")
            raise
    
    def disconnect(self):
        """Desconectar ADB"""
        logger.info("📱 Desconectando ADB...")
        
        try:
            subprocess.run(
                [self.adb_path, "disconnect"],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("✅ ADB desconectado")
        
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Erro ao desconectar: {e.stderr}")
    
    def disable_phantom_process_killer(self):
        """
        Desativar Phantom Process Killer (PPK).
        
        Comando:
        device_config put activity_manager max_phantom_processes 2147483647
        """
        logger.info("🛡️  Desativando Phantom Process Killer...")
        
        commands = [
            # Aumentar limite de processos fantasmas para máximo (2^31)
            "device_config put activity_manager max_phantom_processes 2147483647",
            
            # Desativar monitoramento de CPU
            "settings put global settings_enable_monitor_phantom_procs false",
            
            # Prevenir sobrescrita de configs durante atualizações diárias
            "device_config set_sync_disabled_for_tests persistent"
        ]
        
        for cmd in commands:
            try:
                subprocess.run(
                    [self.adb_path, "shell", cmd],
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info(f"✅ Comando executado: {cmd}")
            
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Erro ao executar: {cmd}\n{e.stderr}")
                raise
    
    def disable_miui_sentinel(self):
        """
        Desativar MiuiSentinelMemoryManager.
        
        Comandos:
        appops set com.miui.powerkeeper GET_USAGE_STATS deny
        settings put global miui_sentinel_memory_manager_enabled 0
        """
        logger.info("🛡️  Desativando MiuiSentinelMemoryManager...")
        
        commands = [
            # Restringir acesso do PowerKeeper a estatísticas de uso
            "appops set com.miui.powerkeeper GET_USAGE_STATS deny",
            
            # Desativar sentinela de memória (HyperOS >3.0.7)
            "settings put global miui_sentinel_memory_manager_enabled 0"
        ]
        
        for cmd in commands:
            try:
                subprocess.run(
                    [self.adb_path, "shell", cmd],
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info(f"✅ Comando executado: {cmd}")
            
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Erro ao executar: {cmd}\n{e.stderr}")
                raise
    
    def verify(self) -> Dict[str, bool]:
        """
        Verificar se otimizações estão ativas.
        
        Returns:
            Dict com status de cada otimização
        """
        logger.info("🔍 Verificando otimizações...")
        
        checks = {
            "phantom_processes": self._check_phantom_processes(),
            "monitor_phantom_procs": self._check_monitor_phantom_procs(),
            "miui_sentinel": self._check_miui_sentinel()
        }
        
        all_passed = all(checks.values())
        
        if all_passed:
            logger.info("✅ Todas as otimizações validadas")
        else:
            for name, passed in checks.items():
                status = "✅" if passed else "❌"
                logger.warning(f"{status} {name}")
        
        return checks
    
    def _check_phantom_processes(self) -> bool:
        """Verificar se limite de processos fantasmas foi aplicado"""
        try:
            result = subprocess.run(
                [self.adb_path, "shell", "device_config", "get", "activity_manager", "max_phantom_processes"],
                capture_output=True,
                text=True
            )
            return "2147483647" in result.stdout
        
        except Exception:
            return False
    
    def _check_monitor_phantom_procs(self) -> bool:
        """Verificar se monitoramento de CPU foi desativado"""
        try:
            result = subprocess.run(
                [self.adb_path, "shell", "settings", "get", "global", "settings_enable_monitor_phantom_procs"],
                capture_output=True,
                text=True
            )
            return "0" in result.stdout
        
        except Exception:
            return False
    
    def _check_miui_sentinel(self) -> bool:
        """Verificar se MiuiSentinel foi desativado"""
        try:
            result = subprocess.run(
                [self.adb_path, "shell", "settings", "get", "global", "miui_sentinel_memory_manager_enabled"],
                capture_output=True,
                text=True
            )
            return "0" in result.stdout
        
        except Exception:
            return False
    
    def get_device_info(self) -> Dict[str, Any]:
        """
        Obter informações do dispositivo.
        
        Returns:
            Dict com informações (modelo, Android, HyperOS)
        """
        try:
            result = subprocess.run(
                [self.adb_path, "shell", "getprop"],
                capture_output=True,
                text=True
            )
            
            # Parse propriedades
            props = {}
            for line in result.stdout.split("\n"):
                if "[" in line and "]" in line:
                    key, value = line.strip("[]").split(": ", 1)
                    props[key] = value
            
            return {
                "model": props.get("ro.product.model", "Unknown"),
                "android_version": props.get("ro.build.version.release", "Unknown"),
                "hyperos_version": props.get("ro.miui.ui.version.name", "Unknown"),
                "sdk_version": props.get("ro.build.version.sdk", "Unknown")
            }
        
        except Exception as e:
            logger.error(f"❌ Erro ao obter informações: {e}")
            return {}


# Instância global
adb_injector = ADBInjector()


if __name__ == "__main__":
    # Conectar
    adb_injector.connect_wireless("192.168.1.100")
    
    # Obter informações
    info = adb_injector.get_device_info()
    print(f"\n📱 Dispositivo: {info}")
    
    # Desativar PPK
    adb_injector.disable_phantom_process_killer()
    
    # Desativar MiuiSentinel
    adb_injector.disable_miui_sentinel()
    
    # Verificar
    checks = adb_injector.verify()
    print(f"\n✅ Validação: {checks}")
    
    # Desconectar
    adb_injector.disconnect()
