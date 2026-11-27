"""Testes offline de src/evaluation/metrics_dashboard.py (A12). Usa SQLite em tmp_path."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.evaluation.metrics_dashboard import MetricsDashboard


@pytest.fixture
def dash(tmp_path: Path) -> MetricsDashboard:
    return MetricsDashboard(db_path=str(tmp_path / "metrics.db"))


def _insert_old(db_path: str, days_ago: int) -> None:
    ts = (datetime.now() - timedelta(days=days_ago)).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO task_executions "
            "(timestamp, task_id, success, elapsed_time_seconds, cost_brl, human_override) "
            "VALUES (?, 'antiga', 0, 999, 9.0, 1)",
            (ts,),
        )


def test_init_creates_schema(dash: MetricsDashboard) -> None:
    with sqlite3.connect(dash.db_path) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"task_executions", "daily_metrics"} <= tables


def test_empty_database_yields_zero_metrics(dash: MetricsDashboard) -> None:
    assert dash.get_task_completion_rate() == 0.0
    assert dash.get_human_override_rate() == 0.0
    assert dash.get_avg_latency_p95() == 0.0
    assert dash.get_avg_cost_per_task() == 0.0


def test_completion_and_override_rates(dash: MetricsDashboard) -> None:
    dash.log_task_completion("a", True, 1.0, 0.1)
    dash.log_task_completion("b", True, 2.0, 0.2, human_override=True)
    dash.log_task_completion("c", False, 3.0, 0.3, error_message="boom")
    dash.log_task_completion("d", True, 4.0, 0.4)

    assert dash.get_task_completion_rate() == pytest.approx(0.75)
    assert dash.get_human_override_rate() == pytest.approx(0.25)
    assert dash.get_avg_cost_per_task() == pytest.approx(0.25)


def test_error_message_is_persisted(dash: MetricsDashboard) -> None:
    dash.log_task_completion("x", False, 1.0, 0.0, error_message="falhou")
    with sqlite3.connect(dash.db_path) as conn:
        row = conn.execute("SELECT success, error_message FROM task_executions").fetchone()
    assert row == (0, "falhou")


def test_latency_p95_picks_high_percentile(dash: MetricsDashboard) -> None:
    for seconds in range(1, 21):
        dash.log_task_completion(f"t{seconds}", True, float(seconds), 0.0)
    assert dash.get_avg_latency_p95() == 19.0


def test_window_excludes_old_executions(dash: MetricsDashboard) -> None:
    dash.log_task_completion("nova", True, 1.0, 0.1)
    _insert_old(dash.db_path, days_ago=30)

    assert dash.get_task_completion_rate(days=7) == 1.0
    assert dash.get_task_completion_rate(days=60) == pytest.approx(0.5)
    assert dash.get_human_override_rate(days=7) == 0.0


def test_generate_report_marks_targets_met(dash: MetricsDashboard) -> None:
    for i in range(10):
        dash.log_task_completion(f"t{i}", True, 10.0, 0.05)

    report = dash.generate_report()

    assert report["task_completion_rate"] == 1.0
    assert report["status"] == {
        "task_completion_rate": "✅",
        "human_override_rate": "✅",
        "latency_p95_seconds": "✅",
        "avg_cost_brl": "✅",
    }


def test_generate_report_flags_targets_missed_and_saves_daily_row(dash: MetricsDashboard) -> None:
    for i in range(4):
        dash.log_task_completion(f"t{i}", False, 400.0, 1.0, human_override=True)

    report = dash.generate_report()

    assert report["status"]["task_completion_rate"] == "⚠️"
    assert report["status"]["human_override_rate"] == "⚠️"
    assert report["status"]["latency_p95_seconds"] == "⚠️"
    assert report["status"]["avg_cost_brl"] == "⚠️"

    with sqlite3.connect(dash.db_path) as conn:
        rows = conn.execute("SELECT date, task_completion_rate FROM daily_metrics").fetchall()
    assert rows == [(datetime.now().strftime("%Y-%m-%d"), 0.0)]


def test_generate_report_twice_same_day_replaces_daily_row(dash: MetricsDashboard) -> None:
    dash.log_task_completion("a", True, 1.0, 0.1)
    dash.generate_report()
    dash.generate_report()
    with sqlite3.connect(dash.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0] == 1


def test_export_report_json_writes_valid_file(dash: MetricsDashboard, tmp_path: Path) -> None:
    dash.log_task_completion("a", True, 1.0, 0.1)
    target = tmp_path / "out" / "report.json"
    target.parent.mkdir()

    returned = dash.export_report_json(days=7, filepath=str(target))

    assert returned == str(target)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["period_days"] == 7
    assert data["task_completion_rate"] == 1.0
    assert data["targets"]["task_completion_rate"] == 0.90
