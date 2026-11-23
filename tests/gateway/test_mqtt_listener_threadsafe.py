"""Regressão A02 — fila MQTT thread-safe (Paho → asyncio)."""

from __future__ import annotations

import asyncio
import json
import threading
from unittest.mock import MagicMock

import pytest

from src.gateway.mqtt_listener import enqueue_mqtt_payload, on_message


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