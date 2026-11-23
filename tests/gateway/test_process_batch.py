"""Regressão A01 — persistência await no gateway."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

if "lancedb" not in sys.modules:
    sys.modules["lancedb"] = ModuleType("lancedb")
    sys.modules["lancedb"].connect = MagicMock()

from src.gateway import fastapi_mqtt_bridge as bridge  # noqa: E402


@pytest.fixture
def sample_telemetry() -> dict:
    return {
        "device_id": "watch-001",
        "timestamp": "2026-11-23T00:00:00Z",
        "metrics": {"heart_rate": 72, "battery": 90},
    }


@pytest.mark.asyncio
async def test_process_batch_awaits_insert_before_success(
    monkeypatch: pytest.MonkeyPatch, sample_telemetry: dict
) -> None:
    insert = AsyncMock()
    insert_done = {"ok": False}

    class FakeDB:
        async def insert(self, data: dict) -> None:
            await insert(data)
            insert_done["ok"] = True

    monkeypatch.setattr(bridge, "db_client", FakeDB())
    await bridge.process_batch([sample_telemetry])
    assert insert.await_count == 1
    assert insert_done["ok"] is True


@pytest.mark.asyncio
async def test_process_batch_raises_when_insert_fails(
    monkeypatch: pytest.MonkeyPatch, sample_telemetry: dict
) -> None:
    class FailDB:
        async def insert(self, _data: dict) -> None:
            raise RuntimeError("persistência indisponível")

    monkeypatch.setattr(bridge, "db_client", FailDB())
    with pytest.raises(RuntimeError, match="persistência"):
        await bridge.process_batch([sample_telemetry])