"""Retriever assíncrono com pool global (mocks)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.yby_seed.memory import retriever


def _async_cm(value: object) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=value)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.mark.asyncio
async def test_fetch_context_uses_global_pool() -> None:
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = [("chunk", "yby_arch", "doc.md")]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = _async_cm(mock_cursor)

    pool = MagicMock()
    pool.connection.return_value = _async_cm(mock_conn)

    vec = [0.1] * 8
    with (
        patch("src.yby_seed.memory.retriever.resources.get_pg_pool", return_value=pool),
        patch("src.yby_seed.memory.retriever.asyncio.to_thread", new=AsyncMock(return_value=vec)),
    ):
        text = await retriever.fetch_context("query", domain="yby_arch", top_k=2)

    assert "chunk" in text
    mock_cursor.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_context_fallback_without_pool() -> None:
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = []
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = _async_cm(mock_cursor)

    vec = [0.2] * 8
    with (
        patch("src.yby_seed.memory.retriever.resources.get_pg_pool", return_value=None),
        patch(
            "src.yby_seed.memory.retriever.AsyncConnection.connect",
            new=AsyncMock(return_value=_async_cm(mock_conn)),
        ),
        patch("src.yby_seed.memory.retriever.asyncio.to_thread", new=AsyncMock(return_value=vec)),
    ):
        text = await retriever.fetch_context("offline")

    assert text == ""
