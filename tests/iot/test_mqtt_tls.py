"""Testes de configuração TLS, ciclo de vida e segurança MQTT (A04 / lifecycle)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.gateway.config import load_settings
from src.iot.client import MQTTClient, _create_paho_client
from src.iot.config import IoTConfig
from src.yby.audio.mqtt_bus import PahoMqttPublisher


def test_iot_config_tls_defaults_and_overrides() -> None:
    cfg_plain = IoTConfig.from_env({"IOT_BROKER_PORT": "1883"})
    assert cfg_plain.use_tls is False

    cfg_tls_port = IoTConfig.from_env({"IOT_BROKER_PORT": "8883"})
    assert cfg_tls_port.use_tls is True

    cfg_tls_override = IoTConfig.from_env({"IOT_BROKER_PORT": "8883", "IOT_USE_TLS": "false"})
    assert cfg_tls_override.use_tls is False

    cfg_tls_certs = IoTConfig.from_env(
        {
            "IOT_BROKER_PORT": "1883",
            "IOT_USE_TLS": "true",
            "IOT_CA_CERTS": "/etc/ssl/ca.pem",
            "IOT_CERTFILE": "/etc/ssl/client.pem",
            "IOT_KEYFILE": "/etc/ssl/client.key",
            "IOT_REQUIRE_TLS": "true",
        }
    )
    assert cfg_tls_certs.use_tls is True
    assert cfg_tls_certs.ca_certs == "/etc/ssl/ca.pem"
    assert cfg_tls_certs.certfile == "/etc/ssl/client.pem"
    assert cfg_tls_certs.keyfile == "/etc/ssl/client.key"
    assert cfg_tls_certs.require_tls is True


def test_iot_config_tls_validation_errors() -> None:
    with pytest.raises(ValueError, match="IOT_CERTFILE"):
        IoTConfig.from_env({"IOT_CERTFILE": "/etc/ssl/client.pem"})

    with pytest.raises(ValueError, match="IOT_REQUIRE_TLS"):
        IoTConfig.from_env({"IOT_BROKER_PORT": "1883", "IOT_REQUIRE_TLS": "true"})


def test_create_paho_client_applies_tls() -> None:
    cfg = IoTConfig.from_env(
        {
            "IOT_BROKER_PORT": "8883",
            "IOT_CA_CERTS": "/tmp/ca.crt",
            "IOT_TLS_INSECURE": "true",
        }
    )
    mock_client = MagicMock()
    with patch("paho.mqtt.client.Client", return_value=mock_client):
        created = _create_paho_client(cfg, "yby-test")

    assert created is mock_client
    mock_client.tls_set.assert_called_once_with(ca_certs="/tmp/ca.crt")
    mock_client.tls_insecure_set.assert_called_once_with(True)


def test_mqtt_client_disconnect_prevents_reconnect_scheduling() -> None:
    cfg = IoTConfig.from_env({"IOT_BROKER_PORT": "1883"})
    mock = MagicMock()
    scheduled: list[float] = []
    client = MQTTClient(cfg, mqtt_client=mock, autoconnect=False, schedule_reconnect=lambda d, _fn: scheduled.append(d))
    client.connect()
    client.disconnect()
    client._on_disconnect(mock, None, 1)
    assert scheduled == []


def test_gateway_settings_mqtt_tls_and_auth() -> None:
    s = load_settings(
        {
            "MQTT_BROKER_PORT": "8883",
            "MQTT_USERNAME": "gw",
            "MQTT_PASSWORD": "pw",
            "MQTT_CA_CERTS": "/etc/ca.pem",
        }
    )
    assert s.MQTT_USE_TLS is True
    assert s.MQTT_USERNAME == "gw"
    assert s.MQTT_PASSWORD == "pw"
    assert s.MQTT_CA_CERTS == "/etc/ca.pem"


@pytest.mark.asyncio
async def test_audio_mqtt_bus_configures_tls() -> None:
    mock_client = MagicMock()
    with patch("paho.mqtt.client.Client", return_value=mock_client):
        pub = PahoMqttPublisher(
            host="broker.local",
            port=8883,
            ca_certs="/tmp/ca.pem",
            tls_insecure=False,
        )
        await pub.publish("yby/audio/out", '{"ok": true}')

    mock_client.tls_set.assert_called_once_with(ca_certs="/tmp/ca.pem")
    mock_client.tls_insecure_set.assert_not_called()
    mock_client.publish.assert_called_once()
