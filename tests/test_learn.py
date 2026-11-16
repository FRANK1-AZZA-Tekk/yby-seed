"""Lote 19: aprendizado diário JSONL + relatório (sem auto-merge)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from src.learn.daily import (
    LearnError,
    append_entry,
    format_report,
    read_entries,
    report_for_day,
)
from src.main import cli


def test_append_and_report(tmp_path: Path) -> None:
    log_path = tmp_path / "learn.jsonl"
    now = 1_700_000_000.0  # fixed UTC day
    append_entry(
        kind="success",
        summary="run ls ok na allowlist",
        log_path=log_path,
        tags=["cli", "safety"],
        now=now,
    )
    append_entry(
        kind="failure",
        summary="ollama off no agente",
        log_path=log_path,
        now=now + 10,
    )
    entries = read_entries(log_path)
    assert len(entries) == 2
    day = entries[0].day
    report = report_for_day(log_path=log_path, day=day)
    assert report.total == 2
    assert report.by_kind["success"] == 1
    assert report.by_kind["failure"] == 1
    assert "não faz merge automático" in report.note
    text = format_report(report)
    assert "run ls ok" in text
    assert "ollama off" in text


def test_kind_invalido_e_segredo(tmp_path: Path) -> None:
    log_path = tmp_path / "learn.jsonl"
    with pytest.raises(LearnError, match="kind inválido"):
        append_entry(kind="merge", summary="x", log_path=log_path)
    with pytest.raises(LearnError, match="segredo"):
        append_entry(
            kind="note",
            summary="chave sk-or-v1-abcdefghijklmnopqrstuvwxyz012345",
            log_path=log_path,
        )
    assert not log_path.exists()


def test_cli_learn_log_and_report(tmp_path: Path) -> None:
    log_path = tmp_path / "learn.jsonl"
    runner = CliRunner()
    logged = runner.invoke(
        cli,
        [
            "learn",
            "log",
            "insight",
            "timeout clamp evita hang",
            "--tag",
            "lote24",
            "--log-path",
            str(log_path),
        ],
    )
    assert logged.exit_code == 0, logged.output
    assert "insight" in logged.output
    assert log_path.is_file()
    row = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert row["kind"] == "insight"
    assert "lote24" in row["tags"]

    day = row["day"]
    report = runner.invoke(
        cli, ["learn", "report", "--day", day, "--log-path", str(log_path)]
    )
    assert report.exit_code == 0, report.output
    assert "não faz merge automático" in report.output
    assert "timeout clamp" in report.output

    as_json = runner.invoke(
        cli,
        ["learn", "report", "--day", day, "--log-path", str(log_path), "--json"],
    )
    assert as_json.exit_code == 0
    payload = json.loads(as_json.output)
    assert payload["total"] == 1
    assert payload["entries"][0]["kind"] == "insight"
