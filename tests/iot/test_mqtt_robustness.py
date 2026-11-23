"""Backoff MQTT, validação segura, flood e dedupe pipeline (mocks)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.iot.client import MQTTClient
from src.iot.config import IoTConfig
from src.iot.handlers import parse_message_safe
from src.iot.mem0_bridge import EpisodeStore, save_episode_via_pipeline
from src.iot.message_queue import BoundedMessageQueue
from src.iot.reconnect import next_reconnect_delay
from src.iot.handlers import SensorEvent, IoTEventType
from src.memory.episode_guard import EpisodeGuard
from src.memory.episode_pipeline import EpisodePipeline
from src.memory.pending_queue import PendingEpisodeQueue


def test_reconnect_delay_exponential_with_jitter() -> None:
    class _Deterministic:
        def uniform(self, _a: float, _b: float) -> float:
            return 0.1

    assert next_reconnect_delay(0, rng=_Deterministic()) == pytest.approx(1.1)
    assert next_reconnect_delay(1, rng=_Deterministic()) == pytest.approx(2.1)
    assert next_reconnect_delay(2, rng=_Deterministic()) == pytest.approx(4.1)
    assert next_reconnect_delay(3, rng=_Deterministic()) == pytest.approx(8.1)


def test_mqtt_reconnect_schedules_with_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduled: list[float] = []

    def capture(delay: float, run) -> None:
        scheduled.append(delay)

    cfg = IoTConfig.from_env(
        {
            "IOT_RECONNECT_MAX_ATTEMPTS": "3",
            "IOT_RECONNECT_BASE_SECONDS": "1",
            "IOT_MAX_QUEUE_SIZE": "10",
        }
    )
    mock = MagicMock()
    client = MQTTClient(
        cfg,
        mqtt_client=mock,
        autoconnect=False,
        schedule_reconnect=capture,
    )
    client._on_disconnect(mock, None, 1)
    client._on_disconnect(mock, None, 1)
    client._on_disconnect(mock, None, 1)
    client._on_disconnect(mock, None, 1)
    assert len(scheduled) == 3
    assert client.reconnect_attempts == 3


def test_mqtt_on_connect_resets_reconnect_attempts() -> None:
    cfg = IoTConfig.from_env({})
    client = MQTTClient(cfg, mqtt_client=MagicMock(), autoconnect=False)
    client._reconnect_attempt = 2
    client._on_connect(MagicMock(), None, None, 0)
    assert client.reconnect_attempts == 0


def test_message_queue_drops_when_full(caplog: pytest.LogCaptureFixture) -> None:
    q = BoundedMessageQueue(max_size=2)
    assert q.offer("t/a", b"1")
    assert q.offer("t/b", b"2")
    assert q.offer("t/c", b"3") is False
    assert len(q) == 2
    with caplog.at_level("WARNING"):
        assert q.offer("t/d", b"4") is False
    assert any("iot_queue_drop" in r.message for r in caplog.records)


def test_parse_message_safe_invalid(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        assert parse_message_safe("yby/sensors/sala/presence", b"{") is None
    assert any("iot_payload_rejected" in r.message for r in caplog.records)


def test_mqtt_client_drops_when_prefilled_queue() -> None:
    cfg = IoTConfig.from_env({"IOT_MAX_QUEUE_SIZE": "2"})
    mock = MagicMock()
    client = MQTTClient(cfg, mqtt_client=mock, autoconnect=False)
    seen: list[str] = []
    client.on_message(lambda topic, _payload: seen.append(topic))
    q = client.message_queue
    q.offer("prefill/a", b"x")
    q.offer("prefill/b", b"y")
    msg = MagicMock(topic="yby/sensors/sala/presence", payload=b'{"value": true}')
    client._on_message(mock, None, msg)
    assert seen == []


def test_save_episode_via_pipeline_single_guard(tmp_path: Path) -> None:
    import requests

    session = MagicMock()
    session.post = MagicMock(side_effect=requests.ConnectionError("down"))
    from src.memory.remote_store import Mem0HttpClient

    remote = Mem0HttpClient("http://mem0.test", session=session)
    queue = PendingEpisodeQueue(tmp_path / "pending.db")
    guard = EpisodeGuard()
    pipe = EpisodePipeline(remote=remote, queue=queue, guard=guard)
    event = SensorEvent(
        sensor_id="sala-pir",
        event_type=IoTEventType.PRESENCE,
        value=True,
        room="sala",
        topic="yby/sensors/sala/presence",
        received_at=1.0,
        raw={"value": True},
    )
    store = EpisodeStore()
    result = save_episode_via_pipeline(event, pipe, guard=store, now=1.0)
    assert result.accepted and result.queued
    assert queue.pending_count() == 1
    # segunda chamada com mesmo evento: guard na ponte rejeita (não duplica na fila)
    dup = save_episode_via_pipeline(event, pipe, guard=store, now=1.5)
    assert not dup.accepted
    queue.close()
    remote.close()


def test_flush_pending_without_second_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        status_code = 200

    class _Session:
        def __init__(self) -> None:
            self.calls = 0
            self.fail = True

        def post(self, url: str, **kwargs: object) -> _Resp:
            import requests

            self.calls += 1
            if self.fail:
                raise requests.ConnectionError("down")
            return _Resp()

        def close(self) -> None:
            pass

    monkeypatch.setattr("src.memory.remote_store.time.sleep", lambda _d: None)
    from src.memory.remote_store import Mem0HttpClient

    session = _Session()
    remote = Mem0HttpClient("http://mem0.test", session=session)
    queue = PendingEpisodeQueue(tmp_path / "q.db")
    guard = EpisodeGuard()
    pipe = EpisodePipeline(remote=remote, queue=queue, guard=guard)
    event = SensorEvent(
        sensor_id="sensor",
        event_type=IoTEventType.TEMPERATURE,
        value=21,
        room="sala",
        topic="yby/sensors/sala/t1/temperature",
        received_at=1.0,
        raw={"value": 21},
    )
    save_episode_via_pipeline(event, pipe, guard=guard, now=1.0)
    assert queue.pending_count() == 1
    session.fail = False
    assert pipe.flush_pending() == 1
    assert queue.pending_count() == 0
    assert session.calls >= 1
    # episódio já aceito não volta à fila no flush
    assert pipe.flush_pending() == 0
    queue.close()
    remote.close()