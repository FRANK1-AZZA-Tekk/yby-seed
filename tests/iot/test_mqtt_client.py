"""Testes IoT/MQTT com mocks (sem broker real)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.iot.client import MQTTClient
from src.iot.config import IoTConfig
from src.iot.handlers import PayloadValidationError, parse_message
from src.iot.langgraph_bridge import SensorStateStore, register_iot_tools
from src.iot.mem0_bridge import EpisodeStore, save_episode
from src.iot.handlers import SensorEvent, IoTEventType


def test_iot_config_from_env_defaults() -> None:
    cfg = IoTConfig.from_env(
        {
            "IOT_BROKER_HOST": "",
            "IOT_BROKER_PORT": "",
            "IOT_USERNAME": "",
            "IOT_PASSWORD": "",
            "IOT_TOPICS": "",
        }
    )
    assert cfg.broker_host == "localhost"
    assert cfg.broker_port == 1883
    assert cfg.username is None
    assert cfg.topics == ["yby/sensors/#"]


def test_iot_config_from_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("IOT_BROKER_HOST", "192.168.1.10")
    monkeypatch.setenv("IOT_BROKER_PORT", "8883")
    monkeypatch.setenv("IOT_USERNAME", "hub")
    monkeypatch.setenv("IOT_PASSWORD", "secret")
    monkeypatch.setenv("IOT_TOPICS", "yby/sensors/#,yby/actuators/#")
    cfg = IoTConfig.from_env()
    assert cfg.broker_host == "192.168.1.10"
    assert cfg.broker_port == 8883
    assert cfg.username == "hub"
    assert cfg.password == "secret"
    assert cfg.topics == ["yby/sensors/#", "yby/actuators/#"]


def test_mqtt_client_connect_subscribe_publish() -> None:
    cfg = IoTConfig.from_env({"IOT_BROKER_HOST": "broker.local", "IOT_BROKER_PORT": "1883"})
    mock = MagicMock()
    client = MQTTClient(cfg, mqtt_client=mock, autoconnect=False)
    client.connect()
    client.subscribe(["yby/sensors/#"])
    client.publish("yby/sensors/sala/temperature", json.dumps({"value": 21.5}))

    mock.connect.assert_called_once_with("broker.local", 1883, keepalive=60)
    mock.loop_start.assert_called_once()
    mock.subscribe.assert_called_with("yby/sensors/#")
    mock.publish.assert_called_once()
    payload = mock.publish.call_args[0][1]
    assert b"21.5" in payload


def test_mqtt_client_on_message_callback() -> None:
    cfg = IoTConfig.from_env({})
    mock = MagicMock()
    client = MQTTClient(cfg, mqtt_client=mock, autoconnect=False)
    received: list[tuple[str, bytes]] = []

    def capture(topic: str, payload: bytes) -> None:
        received.append((topic, payload))

    client.on_message(capture)
    message = MagicMock(topic="yby/sensors/sala/presence", payload=b'{"value": true}')
    client._on_message(mock, None, message)
    assert received == [("yby/sensors/sala/presence", b'{"value": true}')]


def test_parse_message_temperature() -> None:
    topic = "yby/sensors/quarto/dht22/temperature"
    payload = json.dumps({"value": 24.2, "unit": "C"})
    event = parse_message(topic, payload)
    assert event.event_type == IoTEventType.TEMPERATURE
    assert event.sensor_id == "dht22"
    assert event.room == "quarto"
    assert event.value == 24.2


def test_parse_message_invalid_json() -> None:
    with pytest.raises(PayloadValidationError, match="JSON"):
        parse_message("yby/sensors/sala/presence", "not-json")


def test_parse_message_missing_value() -> None:
    with pytest.raises(PayloadValidationError, match="value"):
        parse_message("yby/sensors/sala/presence", "{}")


def test_save_episode_dedupe_and_rate_limit() -> None:
    store = EpisodeStore()
    saved: list[str] = []
    event = SensorEvent(
        sensor_id="sala-pir",
        event_type=IoTEventType.PRESENCE,
        value=True,
        room="sala",
        topic="yby/sensors/sala/presence",
        received_at=1000.0,
        raw={"value": True},
    )
    t0 = 1000.0
    assert save_episode(event, save_fn=lambda text, _: saved.append(text), store=store, now=t0)
    assert save_episode(event, save_fn=lambda text, _: saved.append(text), store=store, now=t0 + 1.0) is False
    assert len(saved) == 1

    for i in range(10):
        ev = SensorEvent(
            sensor_id="sala-pir",
            event_type=IoTEventType.PRESENCE,
            value=i,
            room="sala",
            topic="yby/sensors/sala/presence",
            received_at=2000.0 + i,
            raw={"value": i},
        )
        save_episode(ev, save_fn=lambda text, _: saved.append(text), store=store, now=2000.0 + i)
    extra = SensorEvent(
        sensor_id="sala-pir",
        event_type=IoTEventType.PRESENCE,
        value=99,
        room="sala",
        topic="yby/sensors/sala/presence",
        received_at=2000.0 + 10,
        raw={"value": 99},
    )
    assert (
        save_episode(extra, save_fn=lambda text, _: saved.append(text), store=store, now=2000.0 + 10)
        is False
    )


def test_mem0_client_mock() -> None:
    mem0 = MagicMock()
    event = SensorEvent(
        sensor_id="porta",
        event_type=IoTEventType.DOOR,
        value="open",
        room="entrada",
        topic="yby/sensors/entrada/porta/door",
        received_at=1.0,
        raw={"value": "open"},
    )
    store = EpisodeStore()
    assert save_episode(event, mem0_client=mem0, store=store, now=1.0)
    mem0.add.assert_called_once()
    assert "porta" in mem0.add.call_args[0][0][0]["content"]


def test_langgraph_register_iot_tools() -> None:
    store = SensorStateStore()
    event = parse_message(
        "yby/sensors/cozinha/mov/motion",
        json.dumps({"value": "detected"}),
    )
    store.update(event)
    tools = register_iot_tools(store)
    names = {item["name"] for item in tools}
    assert names == {"get_sensor_state", "list_sensors"}
    get_tool = next(t for t in tools if t["name"] == "get_sensor_state")
    list_tool = next(t for t in tools if t["name"] == "list_sensors")
    state = json.loads(get_tool["func"]("mov"))
    assert state["value"] == "detected"
    sensors = json.loads(list_tool["func"]())
    assert len(sensors) == 1