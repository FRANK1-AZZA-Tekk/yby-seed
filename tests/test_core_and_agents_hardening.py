"""Testes de hardening de engine, core e agents (A08, A10, A15)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.agents.bayesian_teaching import BayesianTeaching
from src.agents.learning_agent import LearningAgent
from src.core.auto_cleanup import AutoCleanup
from src.core.memory_allocator import MemoryAllocator
from src.engine.hybrid import engine_from_env


def test_engine_from_env_fails_closed_without_confirm_or_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YBY_CLOUD_API_KEY", "sk-test")
    monkeypatch.setenv("YBY_CLOUD_REQUIRE_CONFIRM", "1")
    engine = engine_from_env()
    try:
        assert engine.confirm_fn("Confirmar?") is False
        assert isinstance(engine.has_tty_fn(), bool)
    finally:
        engine.close()


def test_memory_allocator_install_requires_confirm_and_enable_is_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alloc = MemoryAllocator(allocator="jemalloc")
    with pytest.raises(PermissionError, match="confirm=True"):
        alloc.install()

    with patch("src.core.memory_allocator.subprocess.run") as run_mock:
        alloc.install(confirm=True)
        run_mock.assert_called_once_with(["sudo", "apt", "install", "-y", "libjemalloc2"], check=True)

    fake_lib = tmp_path / "libjemalloc.so"
    fake_lib.write_text("", encoding="utf-8")
    alloc.lib_path = str(fake_lib)

    bashrc = tmp_path / ".bashrc"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LD_PRELOAD", raising=False)

    alloc.enable()
    assert not bashrc.exists()
    assert str(fake_lib) in os.environ["LD_PRELOAD"]

    alloc.enable(persist=True)
    alloc.enable(persist=True)
    content = bashrc.read_text(encoding="utf-8")
    assert content.count(f'export LD_PRELOAD="{fake_lib}"') == 1

    alloc.disable()
    assert str(fake_lib) not in os.environ.get("LD_PRELOAD", "")


def test_memory_allocator_benchmark_uses_minimal_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TOP_SECRET_API_KEY", "should-not-leak")
    alloc = MemoryAllocator(allocator="jemalloc")
    fake_lib = tmp_path / "libjemalloc.so"
    fake_lib.write_text("", encoding="utf-8")
    alloc.lib_path = str(fake_lib)

    fake_result = MagicMock(stdout="Time: 0.42s\nMemory: 128MB\nFragmentation: 5%\n")
    with patch("src.core.memory_allocator.subprocess.run", return_value=fake_result) as run_mock:
        metrics = alloc.benchmark("test_alloc.py")

    assert metrics == {"time_sec": 0.42, "memory_mb": 128, "fragmentation_pct": 5}
    passed_env = run_mock.call_args.kwargs["env"]
    assert "TOP_SECRET_API_KEY" not in passed_env
    assert passed_env["LD_PRELOAD"] == str(fake_lib)


def test_auto_cleanup_minimal_env_and_no_redis_debug_sleep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TOP_SECRET_TOKEN", "do-not-leak")
    cleanup = AutoCleanup(log_dir=str(tmp_path), db_url="postgresql://user:pass@localhost:5432/yby")

    with patch("src.core.auto_cleanup.subprocess.run") as run_mock:
        cleanup.vacuum_database()

    passed_env = run_mock.call_args.kwargs["env"]
    assert "TOP_SECRET_TOKEN" not in passed_env
    assert passed_env["PGPASSWORD"] == "pass"

    fake_redis = MagicMock()
    fake_redis.info.return_value = {"expired_keys": 3, "evicted_keys": 0}
    redis_mod = ModuleType("redis")
    redis_mod.Redis = MagicMock(return_value=fake_redis)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "redis", redis_mod)
    cleanup.cleanup_redis_cache()

    fake_redis.execute_command.assert_not_called()
    fake_redis.info.assert_called_once_with("stats")


def test_learning_agent_embedding_and_bayesian_teaching() -> None:
    agent = LearningAgent(db_url="")
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {"embedding": [0.3] * 384}

    with patch("src.agents.learning_agent.httpx.post", return_value=fake_resp):
        vec_ok = agent._generate_embedding("backup script")
        assert len(vec_ok) == 384
        assert vec_ok[0] == 0.3

    with patch("src.agents.learning_agent.httpx.post", side_effect=httpx.ConnectError("offline")):
        vec_fb = agent._generate_embedding("backup script")
        assert len(vec_fb) == 384
        assert any(v != 0.0 for v in vec_fb)
        assert abs(sum(v * v for v in vec_fb) - 1.0) < 1e-6

    bt = BayesianTeaching()
    assert bt.converge("backup_automation_success", max_iterations=0) == 0
    bt.update("backup_automation_success", "success")
    assert bt.beliefs["backup_automation_success"] > 0.5
    bt.reset(None)
    assert bt.beliefs["backup_automation_success"] == 0.5
