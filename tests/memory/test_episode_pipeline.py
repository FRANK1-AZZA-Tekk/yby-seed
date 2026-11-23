"""Mem0: dedupe, fila local, retry (mocks)."""

from __future__ import annotations

from pathlib import Path
import pytest
import requests

from src.memory.episode_guard import EpisodeGuard
from src.memory.episode_pipeline import EpisodePipeline
from src.memory.pending_queue import PendingEpisodeQueue
from src.memory.remote_store import Mem0HttpClient, RemoteStoreError, post_with_retry


class _Resp:
    def __init__(self, status: int = 200) -> None:
        self.status_code = status


class _Session:
    def __init__(self, responses: list[int] | None = None, *, fail: bool = False) -> None:
        self.fail = fail
        self._codes = list(responses or [200])
        self.posts: list[dict] = []
        self.closed = False

    def post(self, url: str, **kwargs: object) -> _Resp:
        self.posts.append({"url": url, **kwargs})
        if self.fail:
            raise requests.ConnectionError("down")
        if not self._codes:
            return _Resp(500)
        code = self._codes.pop(0)
        return _Resp(code)

    def close(self) -> None:
        self.closed = True


def test_episode_guard_dedupe_and_rate_limit() -> None:
    guard = EpisodeGuard()
    t0 = 1000.0
    assert guard.should_accept("fonte-a", "mesmo", now=t0)
    assert guard.should_accept("fonte-a", "mesmo", now=t0 + 1.0) is False
    for i in range(10):
        assert guard.should_accept("fonte-b", f"v{i}", now=2000.0 + i)
    assert guard.should_accept("fonte-b", "v-extra", now=2000.0 + 10) is False


def test_pending_queue_persists(tmp_path: Path) -> None:
    q = PendingEpisodeQueue(tmp_path / "pending.db")
    eid = q.enqueue("sala", {"messages": [{"role": "user", "content": "oi"}]}, now=1.0)
    assert eid >= 1
    assert q.pending_count() == 1
    batch = q.list_batch()
    assert len(batch) == 1
    q.remove(batch[0].id)
    assert q.pending_count() == 0
    q.close()


def test_post_with_retry_on_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.memory.remote_store.time.sleep", lambda _d: None)
    session = _Session([503, 200])
    post_with_retry(session, "http://mem0.test/v1/memories", json_body={"x": 1})
    assert len(session.posts) == 2


def test_pipeline_queues_on_remote_failure(tmp_path: Path) -> None:
    session = _Session(fail=True)
    remote = Mem0HttpClient("http://mem0.test", session=session)
    queue = PendingEpisodeQueue(tmp_path / "q.db")
    pipe = EpisodePipeline(remote=remote, queue=queue)
    result = pipe.save("iot/sala", "temperatura 22", {"value": 22}, now=1.0)
    assert result.accepted and result.queued and not result.persisted
    assert queue.pending_count() == 1
    queue.close()
    remote.close()


def test_pipeline_flush_after_recovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.memory.remote_store.time.sleep", lambda _d: None)
    session = _Session(fail=True)
    remote = Mem0HttpClient("http://mem0.test", session=session)
    queue = PendingEpisodeQueue(tmp_path / "q.db")
    pipe = EpisodePipeline(remote=remote, queue=queue)
    pipe.save("vault", "nota", None, now=1.0)
    session.fail = False
    session._codes = [200]
    assert pipe.flush_pending() == 1
    assert queue.pending_count() == 0
    queue.close()


def test_post_raises_after_three_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.memory.remote_store.time.sleep", lambda _d: None)
    with pytest.raises(RemoteStoreError):
        post_with_retry(_Session(fail=True), "http://x", json_body={})