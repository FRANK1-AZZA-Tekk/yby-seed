"""Testes offline de src/monitoring/metrics_dashboard.py (A12).

O módulo sobe um servidor Prometheus e cria uma instância global no import.
Por isso o import é feito com um `prometheus_client` falso, sem abrir portas
nem depender do pacote real.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import pytest


class _Value:
    def __init__(self) -> None:
        self._v = 0.0

    def get(self) -> float:
        return self._v


class _FakeGauge:
    def __init__(self, name: str, doc: str, **_: Any) -> None:
        self.name = name
        self._value = _Value()

    def set(self, value: float) -> None:
        self._value._v = value


class _FakeCounter(_FakeGauge):
    def inc(self, amount: float = 1) -> None:
        self._value._v += amount


class _FakeHistogram:
    def __init__(self, name: str, doc: str, **_: Any) -> None:
        self.name = name
        self.observed: list[float] = []

    def observe(self, value: float) -> None:
        self.observed.append(value)


@pytest.fixture
def dashboard_module(monkeypatch: pytest.MonkeyPatch):
    fake = ModuleType("prometheus_client")
    start_server = MagicMock()
    fake.start_http_server = start_server  # type: ignore[attr-defined]
    fake.Gauge = _FakeGauge  # type: ignore[attr-defined]
    fake.Counter = _FakeCounter  # type: ignore[attr-defined]
    fake.Histogram = _FakeHistogram  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "prometheus_client", fake)
    monkeypatch.delitem(sys.modules, "src.monitoring.metrics_dashboard", raising=False)
    module = importlib.import_module("src.monitoring.metrics_dashboard")
    yield module, start_server
    sys.modules.pop("src.monitoring.metrics_dashboard", None)


def test_import_starts_prometheus_server_once_on_default_port(dashboard_module) -> None:
    module, start_server = dashboard_module
    start_server.assert_called_once_with(8001)
    assert module.metrics_dashboard.port == 8001


def test_custom_port_is_forwarded_to_prometheus(dashboard_module) -> None:
    module, start_server = dashboard_module
    start_server.reset_mock()
    dash = module.MetricsDashboard(port=9100)
    start_server.assert_called_once_with(9100)
    assert dash.port == 9100


def test_updates_are_reflected_in_get_all_metrics(dashboard_module) -> None:
    module, _ = dashboard_module
    dash = module.MetricsDashboard(port=9101)

    dash.update_queue_size(7)
    dash.update_websocket_clients(3)
    dash.update_vram_used(2048.5)
    dash.update_cpu_ram_disk(cpu=41.0, ram=55.5, disk=62.25)

    metrics = dash.get_all_metrics()
    assert metrics["queue_size"] == 7
    assert metrics["websocket_clients"] == 3
    assert metrics["vram_used_mb"] == 2048.5
    assert metrics["cpu_percent"] == 41.0
    assert metrics["ram_percent"] == 55.5
    assert metrics["disk_percent"] == 62.25


def test_increment_errors_accumulates_default_and_explicit_counts(dashboard_module) -> None:
    module, _ = dashboard_module
    dash = module.MetricsDashboard(port=9102)
    before = dash.get_all_metrics()["errors_total"]

    dash.increment_errors()
    dash.increment_errors(count=4)

    assert dash.get_all_metrics()["errors_total"] == before + 5


def test_observe_latency_records_value_in_histogram(dashboard_module) -> None:
    module, _ = dashboard_module
    dash = module.MetricsDashboard(port=9103)
    dash.observe_latency(123.4)
    assert module.LATENCY_MS.observed[-1] == 123.4


def test_get_all_metrics_exposes_expected_keys(dashboard_module) -> None:
    module, _ = dashboard_module
    keys = set(module.MetricsDashboard(port=9104).get_all_metrics())
    assert keys == {
        "queue_size",
        "websocket_clients",
        "vram_used_mb",
        "cpu_percent",
        "ram_percent",
        "disk_percent",
        "errors_total",
    }
