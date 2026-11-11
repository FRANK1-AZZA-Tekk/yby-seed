"""
Metrics Dashboard — exportação Prometheus (opcional / lazy).

Não inicia servidor HTTP no import. prometheus_client é opcional.
"""

from __future__ import annotations

import logging
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MetricsDashboard:
    """Dashboard de métricas para Grafana (lazy)."""

    def __init__(self, port: int = 8001, start_server: bool = False):
        self.port = port
        self._started = False
        self._gauges: dict[str, Any] = {}
        self._histogram = None
        self._errors = None
        self._prom_ready = False

        try:
            from prometheus_client import Counter, Gauge, Histogram

            self._gauges = {
                "queue_size": Gauge("yby_queue_size", "Tamanho da fila MQTT"),
                "websocket_clients": Gauge(
                    "yby_websocket_clients", "Número de clientes WebSocket"
                ),
                "vram_used_mb": Gauge("yby_vram_used_mb", "VRAM usada em MB"),
                "cpu_percent": Gauge("yby_cpu_percent", "Uso de CPU em %"),
                "ram_percent": Gauge("yby_ram_percent", "Uso de RAM em %"),
                "disk_percent": Gauge("yby_disk_percent", "Uso de disco em %"),
            }
            self._histogram = Histogram(
                "yby_latency_ms",
                "Latência em ms",
                buckets=[100, 250, 500, 1000, 2500, 5000],
            )
            self._errors = Counter("yby_errors_total", "Total de erros")
            self._prom_ready = True
        except ImportError:
            logger.warning(
                "prometheus_client ausente — MetricsDashboard em modo no-op."
            )

        if start_server:
            self.start()

    def start(self) -> None:
        if self._started or not self._prom_ready:
            return
        from prometheus_client import start_http_server

        start_http_server(self.port)
        self._started = True
        logger.info("📊 Prometheus metrics server iniciado na porta %s", self.port)

    def update_queue_size(self, size: int) -> None:
        if self._prom_ready:
            self._gauges["queue_size"].set(size)

    def update_websocket_clients(self, count: int) -> None:
        if self._prom_ready:
            self._gauges["websocket_clients"].set(count)

    def update_vram_used(self, mb: float) -> None:
        if self._prom_ready:
            self._gauges["vram_used_mb"].set(mb)

    def update_cpu_ram_disk(self, cpu: float, ram: float, disk: float) -> None:
        if self._prom_ready:
            self._gauges["cpu_percent"].set(cpu)
            self._gauges["ram_percent"].set(ram)
            self._gauges["disk_percent"].set(disk)

    def observe_latency(self, ms: float) -> None:
        if self._prom_ready and self._histogram is not None:
            self._histogram.observe(ms)

    def increment_errors(self) -> None:
        if self._prom_ready and self._errors is not None:
            self._errors.inc()

    def snapshot(self) -> dict[str, Any]:
        if not self._prom_ready:
            return {"prometheus": False}
        return {
            "queue_size": self._gauges["queue_size"]._value.get(),
            "websocket_clients": self._gauges["websocket_clients"]._value.get(),
            "vram_used_mb": self._gauges["vram_used_mb"]._value.get(),
            "cpu_percent": self._gauges["cpu_percent"]._value.get(),
            "ram_percent": self._gauges["ram_percent"]._value.get(),
            "disk_percent": self._gauges["disk_percent"]._value.get(),
            "errors_total": self._errors._value.get() if self._errors else 0,
        }


def get_metrics_dashboard(port: int = 8001, start_server: bool = False) -> MetricsDashboard:
    return MetricsDashboard(port=port, start_server=start_server)
