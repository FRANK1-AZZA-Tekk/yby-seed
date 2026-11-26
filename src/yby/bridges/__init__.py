"""Pontes de protocolo universais -> MQTT (BLE GATT, tráfego IoT local e ADB/Termux)."""

from __future__ import annotations

from src.yby.bridges.ble_bridge import (
    BleakTransport,
    BleBridgeError,
    BleDiscoveredDevice,
    BleGattBridge,
    BleTransport,
)
from src.yby.bridges.schemas import (
    TOPIC_BLE_CMD,
    TOPIC_BLE_TELEMETRY,
    TOPIC_TRAFFIC_EVENT,
    BleCharacteristicProfile,
    BleCommandMessage,
    BleDeviceProfile,
    BleTelemetryEvent,
    NormalizedTrafficEvent,
    TrafficAlertRule,
)
from src.yby.bridges.traffic_bridge import (
    AdbEventBridge,
    TrafficBridgeError,
    YbyTrafficAddon,
    scrub_headers_and_payload,
)

__all__ = [
    "TOPIC_BLE_CMD",
    "TOPIC_BLE_TELEMETRY",
    "TOPIC_TRAFFIC_EVENT",
    "AdbEventBridge",
    "BleBridgeError",
    "BleCharacteristicProfile",
    "BleCommandMessage",
    "BleDeviceProfile",
    "BleDiscoveredDevice",
    "BleGattBridge",
    "BleTelemetryEvent",
    "BleTransport",
    "BleakTransport",
    "NormalizedTrafficEvent",
    "TrafficAlertRule",
    "TrafficBridgeError",
    "YbyTrafficAddon",
    "scrub_headers_and_payload",
]
