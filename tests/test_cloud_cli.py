"""S5: yby cloud report / prune (#42)."""

from __future__ import annotations

from click.testing import CliRunner

from src.engine.cloud_cli import cloud_cli
from src.engine.cloud_usage_db import CloudUsageRegistry
from src.engine.cloud_usage_log import EVENT_COMPLETED, EVENT_FAILED, utc_timestamp
from src.engine.cloud_usage_report import (
    build_cloud_usage_report,
    format_cloud_usage_report,
)
from src.main import cli


def test_build_and_format_report(tmp_path, monkeypatch) -> None:
    db = tmp_path / "cloud.sqlite3"
    jsonl = tmp_path / "cloud.jsonl"
    reg = CloudUsageRegistry(db)
    reg.insert_event(
        {
            "timestamp": utc_timestamp(),
            "provider": "openrouter",
            "model": "openrouter/free",
            "purpose": "route_cloud",
            "input_tokens_estimate": 40,
            "output_tokens_estimate": 10,
            "estimated_cost_usd": 0.0,
            "result": EVENT_COMPLETED,
        }
    )
    reg.close()

    env = {
        "YBY_CLOUD_DB_PATH": str(db),
        "YBY_CLOUD_LOG_PATH": str(jsonl),
        "YBY_CLOUD_JSONL_MIRROR": "0",
        "YBY_CLOUD_ALLOW_VAULT": "0",
        "YBY_CLOUD_MODE": "ask",
        "YBY_CLOUD_RETENTION_DAYS": "90",
        "YBY_CLOUD_MONTHLY_COST_USD_LIMIT": "10.00",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    report = build_cloud_usage_report(env)
    assert report.db_exists is True
    assert report.event_count == 1
    assert report.by_status.get("completed") == 1
    assert report.day_tokens == 50
    text = format_cloud_usage_report(report)
    assert "YBY cloud usage" in text
    assert "events: 1" in text
    assert "allow_vault: 0" in text


def test_cli_report_and_prune(tmp_path, monkeypatch) -> None:
    db = tmp_path / "cloud.sqlite3"
    reg = CloudUsageRegistry(db)
    now = 1_700_000_000.0
    old = now - (120 * 86400)
    reg.insert_event(
        {
            "timestamp": old,
            "provider": "openrouter",
            "model": "m",
            "purpose": "t",
            "input_tokens_estimate": 1,
            "output_tokens_estimate": 0,
            "result": EVENT_COMPLETED,
        }
    )
    reg.insert_event(
        {
            "timestamp": old,
            "provider": "openrouter",
            "model": "m",
            "purpose": "t",
            "input_tokens_estimate": 1,
            "output_tokens_estimate": 0,
            "result": EVENT_FAILED,
        }
    )
    reg.close()

    monkeypatch.setenv("YBY_CLOUD_DB_PATH", str(db))
    monkeypatch.setenv("YBY_CLOUD_LOG_PATH", str(tmp_path / "x.jsonl"))
    monkeypatch.setenv("YBY_CLOUD_RETENTION_DAYS", "90")

    runner = CliRunner()
    report_result = runner.invoke(cli, ["cloud", "report"])
    assert report_result.exit_code == 0, report_result.output
    assert "events: 2" in report_result.output

    dry = runner.invoke(cloud_cli, ["prune", "--dry-run", "--days", "90"])
    assert dry.exit_code == 0, dry.output
    assert "candidatos" in dry.output

    # Fix "now" indirectly: prune with large retention keeps rows; small days deletes.
    # Use retention_days=30 relative to wall clock — old stamp is 120d ago so deletes.
    pruned = runner.invoke(cloud_cli, ["prune", "--days", "30"])
    assert pruned.exit_code == 0, pruned.output
    assert "apagados" in pruned.output

    after = CloudUsageRegistry(db)
    assert after.count_events() == 0
    after.close()


def test_prune_dry_run_on_registry(tmp_path) -> None:
    reg = CloudUsageRegistry(tmp_path / "db.sqlite3")
    now = 1_700_000_000.0
    reg.insert_event(
        {
            "timestamp": now - (200 * 86400),
            "provider": "openrouter",
            "model": "m",
            "purpose": "t",
            "input_tokens_estimate": 1,
            "output_tokens_estimate": 0,
            "result": EVENT_COMPLETED,
        }
    )
    assert reg.prune(retention_days=90, now=now, dry_run=True) == 1
    assert reg.count_events() == 1
    assert reg.prune(retention_days=90, now=now, dry_run=False) == 1
    assert reg.count_events() == 0
    reg.close()
