"""CLI de observabilidade sobre cloud_usage.jsonl (lote 22)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from click.testing import CliRunner

from src.engine.budget import CloudBudget
from src.engine.cloud_usage_log import EVENT_BLOCKED_LOCAL_ONLY, EVENT_COMPLETED
from src.main import cli
from src.obs.usage import format_events, format_summary, read_events, summarize


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "timestamp": time.time(),
        "provider": "openrouter",
        "model": "openrouter/free",
        "purpose": "route_cloud",
        "input_tokens_estimate": 10,
        "output_tokens_estimate": 5,
        "result": EVENT_COMPLETED,
        "tokens_source": "estimate",
    }
    base.update(overrides)
    return base


def test_summarize_and_format(tmp_path: Path) -> None:
    log_path = tmp_path / "cloud_usage.jsonl"
    rows = [
        _row(result=EVENT_COMPLETED, input_tokens_estimate=100, output_tokens_estimate=50),
        _row(result=EVENT_BLOCKED_LOCAL_ONLY, input_tokens_estimate=0, output_tokens_estimate=0),
        "not-json",
    ]
    log_path.write_text(
        "".join(
            (json.dumps(row) + "\n") if isinstance(row, dict) else row + "\n" for row in rows
        ),
        encoding="utf-8",
    )
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "ask",
            "YBY_CLOUD_LOG_PATH": str(log_path),
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "200000",
            "YBY_CLOUD_WARN_TOKEN_LIMIT": "150000",
        }
    )
    report = summarize(log_path=log_path, budget=budget)
    assert report.event_count == 2
    assert report.completed_count == 1
    assert report.blocked_count == 1
    assert report.month_tokens == 150
    text = format_summary(report)
    assert "ask" in text
    assert "150/200000" in text
    assert "cloud_completed=1" in text

    events = read_events(log_path)
    listing = format_events(events, limit=10)
    assert "cloud_completed" in listing
    assert "cloud_blocked_local_only" in listing


def test_cli_usage_summary_and_tail(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "usage.jsonl"
    log_path.write_text(json.dumps(_row()) + "\n", encoding="utf-8")
    monkeypatch.setenv("YBY_CLOUD_LOG_PATH", str(log_path))
    monkeypatch.setenv("YBY_CLOUD_MODE", "local_only")

    runner = CliRunner()
    summary = runner.invoke(cli, ["usage"])
    assert summary.exit_code == 0, summary.output
    assert "local_only" in summary.output
    assert "eventos:" in summary.output

    tail = runner.invoke(cli, ["usage", "tail", "--limit", "5"])
    assert tail.exit_code == 0, tail.output
    assert "cloud_completed" in tail.output
    assert "route_cloud" in tail.output
