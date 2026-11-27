"""Regressão A02 — fila MQTT thread-safe (Paho → asyncio)."""

from __future__ import annotations

import asyncio
import json
import threading
from unittest.mock import MagicMock, patch

import pytest

from src.gateway.config import Settings
from src.gateway.mqtt_listener import enqueue_mqtt_payload, mqtt_listener, on_message


@pytest.mark.asyncio
async def test_on_message_from_paho_thread_delivers_to_asyncio_queue() -> None:
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=10)
    loop = asyncio.get_running_loop()
    userdata = {"queue": queue, "loop": loop}
    body = {"device_id": "w1", "timestamp": "t", "metrics": {}}
    msg = MagicMock(topic="yby/telemetry", payload=json.dumps(body).encode("utf-8"), qos=1)

    def paho_thread() -> None:
        on_message(MagicMock(), userdata, msg)

    thread = threading.Thread(target=paho_thread, name="paho-mock")
    thread.start()
    for _ in range(50):
        if queue.qsize() > 0:
            break
        await asyncio.sleep(0.01)
    thread.join(timeout=2.0)
    assert not thread.is_alive()
    assert queue.qsize() == 1
    item = await queue.get()
    assert item["device_id"] == "w1"
    assert item["_metadata"]["topic"] == "yby/telemetry"


@pytest.mark.asyncio
async def test_enqueue_drops_when_queue_full_logs(caplog: pytest.LogCaptureFixture) -> None:
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=1)
    loop = asyncio.get_running_loop()
    queue.put_nowait({"prefill": True})

  # segunda mensagem deve ser descartada no loop
    with caplog.at_level("WARNING"):
        enqueue_mqtt_payload(loop, queue, {"device_id": "w2"})
        await asyncio.sleep(0.05)
    assert queue.qsize() == 1
    assert any("iot_mqtt_gateway_queue_drop" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_concurrent_callbacks_shutdown_without_deadlock() -> None:
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=100)
    loop = asyncio.get_running_loop()
    userdata = {"queue": queue, "loop": loop}
    barrier = threading.Barrier(3)

    def worker(i: int) -> None:
        barrier.wait(timeout=2)
        msg = MagicMock(
            topic=f"yby/t{i}",
            payload=json.dumps({"device_id": f"w{i}", "timestamp": "t", "metrics": {}}).encode(),
            qos=0,
        )
        on_message(MagicMock(), userdata, msg)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    await asyncio.sleep(0.1)
    for t in threads:
        t.join(timeout=3.0)
        assert not t.is_alive()
    assert queue.qsize() == 3


@pytest.mark.asyncio
async def test_enqueue_ignores_closed_loop() -> None:
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=5)
    closed_loop = asyncio.new_event_loop()
    closed_loop.close()
    enqueue_mqtt_payload(closed_loop, queue, {"device_id": "w1"})
    assert queue.qsize() == 0


@pytest.mark.asyncio
async def test_on_message_ignores_non_dict_json(caplog: pytest.LogCaptureFixture) -> None:
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=5)
    loop = asyncio.get_running_loop()
    userdata = {"queue": queue, "loop": loop}
    msg = MagicMock(topic="yby/telemetry", payload=b"[1, 2, 3]", qos=0)
    with caplog.at_level("WARNING"):
        on_message(MagicMock(), userdata, msg)
        await asyncio.sleep(0.02)
    assert queue.qsize() == 0
    assert any("iot_mqtt_gateway_invalid_payload_type" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_mqtt_listener_lifecycle_tls_and_clean_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    import paho.mqtt.client as real_mqtt

    from src.gateway import mqtt_listener as listener_mod

    tls_settings = Settings(
        MQTT_BROKER_HOST="broker.internal",
        MQTT_BROKER_PORT=8883,
        MQTT_USERNAME="gw-user",
        MQTT_PASSWORD="secret",
        MQTT_USE_TLS=True,
        MQTT_CA_CERTS="/etc/ssl/ca.pem",
    )
    monkeypatch.setattr(listener_mod, "settings", tls_settings)

    created_clients: list[real_mqtt.Client] = []
    real_client_cls = real_mqtt.Client

    def _build_client(*args, **kwargs):
        c = real_client_cls(*args, **kwargs)
        c.connect = MagicMock()
        c.loop_start = MagicMock()
        c.loop_stop = MagicMock()
        c.disconnect = MagicMock()
        c.tls_set = MagicMock()
        c.username_pw_set = MagicMock()
        created_clients.append(c)
        return c

    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=10)
    with patch("src.gateway.mqtt_listener.mqtt.Client", side_effect=_build_client):
        task = asyncio.create_task(mqtt_listener(queue))
        await asyncio.sleep(0.05)
        assert not task.done(), "mqtt_listener deve permanecer ativo até o cancelamento do lifespan"
        assert len(created_clients) == 1
        client = created_clients[0]
        client.username_pw_set.assert_called_once_with("gw-user", "secret")
        client.tls_set.assert_called_once_with(ca_certs="/etc/ssl/ca.pem")
        client.connect.assert_called_once_with(host="broker.internal", port=8883, keepalive=60)
        client.loop_start.assert_called_once()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        client.loop_stop.assert_called_once()
        client.disconnect.assert_called_once()