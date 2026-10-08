"""
Metrics Dashboard — Dashboard de métricas (Grafana)

Responsabilidade:
- Exportar métricas para Grafana
- Visualizar telemetria em tempo real
- Alertas (CPU >90%, RAM >90%, disco >80%)

Arquitetura:
[FastAPI Gateway] → [Prometheus] → [Grafana] → [Dashboard]

Métricas Exportadas:
- queue_size (FastAPI)
- websocket_clients
- vram_used_mb (GPU)
- cpu_percent, ram_percent, disk_percent
- latency_ms (RAG, LLM)

Licença: MIT
"""

from prometheus_client import start_http_server, Gauge, Counter, Histogram
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Métricas Prometheus
QUEUE_SIZE = Gauge("yby_queue_size", "Tamanho da fila MQTT")
WEBSOCKET_CLIENTS = Gauge("yby_websocket_clients", "Número de clientes WebSocket")
VRAM_USED = Gauge("yby_vram_used_mb", "VRAM usada em MB")

CPU_PERCENT = Gauge("yby_cpu_percent", "Uso de CPU em %")
RAM_PERCENT = Gauge("yby_ram_percent", "Uso de RAM em %")
DISK_PERCENT = Gauge("yby_disk_percent", "Uso de disco em %")

LATENCY_MS = Histogram("yby_latency_ms", "Latência em ms", buckets=[100, 250, 500, 1000, 2500, 5000])

ERRORS_TOTAL = Counter("yby_errors_total", "Total de erros")


class MetricsDashboard:
    """
    Dashboard de métricas para Grafana.
    """
    
    def __init__(self, port: int = 8001):
        """
        Inicializar dashboard.
        
        Args:
            port: Porta do Prometheus metrics server
        """
        self.port = port
        
        # Iniciar servidor Prometheus
        start_http_server(port)
        logger.info(f"📊 Prometheus metrics server iniciado na porta {port}")
    
    def update_queue_size(self, size: int):
        """
        Atualizar tamanho da fila.
        
        Args:
            size: Tamanho da fila
        """
        QUEUE_SIZE.set(size)
        logger.debug(f"📊 Queue size: {size}")
    
    def update_websocket_clients(self, count: int):
        """
        Atualizar número de clientes WebSocket.
        
        Args:
            count: Número de clientes
        """
        WEBSOCKET_CLIENTS.set(count)
        logger.debug(f"📊 WebSocket clients: {count}")
    
    def update_vram_used(self, mb: float):
        """
        Atualizar VRAM usada.
        
        Args:
            mb: VRAM em MB
        """
        VRAM_USED.set(mb)
        logger.debug(f"📊 VRAM used: {mb}MB")
    
    def update_cpu_ram_disk(self, cpu: float, ram: float, disk: float):
        """
        Atualizar CPU, RAM, disco.
        
        Args:
            cpu: CPU em %
            ram: RAM em %
            disk: Disco em %
        """
        CPU_PERCENT.set(cpu)
        RAM_PERCENT.set(ram)
        DISK_PERCENT.set(disk)
        logger.debug(f"📊 CPU: {cpu}%, RAM: {ram}%, Disk: {disk}%")
    
    def observe_latency(self, ms: float):
        """
        Observar latência.
        
        Args:
            ms: Latência em ms
        """
        LATENCY_MS.observe(ms)
        logger.debug(f"📊 Latency: {ms}ms")
    
    def increment_errors(self, count: int = 1):
        """
        Incrementar contador de erros.
        
        Args:
            count: Número de erros
        """
        ERRORS_TOTAL.inc(count)
        logger.warning(f"📊 Errors: {count}")
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Obter todas as métricas.
        
        Returns:
            Dict com métricas
        """
        return {
            "queue_size": QUEUE_SIZE._value.get(),
            "websocket_clients": WEBSOCKET_CLIENTS._value.get(),
            "vram_used_mb": VRAM_USED._value.get(),
            "cpu_percent": CPU_PERCENT._value.get(),
            "ram_percent": RAM_PERCENT._value.get(),
            "disk_percent": DISK_PERCENT._value.get(),
            "errors_total": ERRORS_TOTAL._value.get()
        }


# Instância global
metrics_dashboard = MetricsDashboard()


if __name__ == "__main__":
    import time
    import random
    
    # Simular métricas
    while True:
        metrics_dashboard.update_queue_size(random.randint(0, 100))
        metrics_dashboard.update_websocket_clients(random.randint(1, 10))
        metrics_dashboard.update_vram_used(random.uniform(2000, 4000))
        metrics_dashboard.update_cpu_ram_disk(
            cpu=random.uniform(30, 90),
            ram=random.uniform(40, 80),
            disk=random.uniform(50, 70)
        )
        metrics_dashboard.observe_latency(random.uniform(100, 2000))
        
        if random.random() < 0.1:
            metrics_dashboard.increment_errors()
        
        time.sleep(5)
