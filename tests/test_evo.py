"""Evo v0.1 — eventos fake, sanitize, SQLite, relatório com Ollama mockado."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.evo.aggregate import aggregate_day
from src.evo.analyze import analyze_day
from src.evo.cli import evo_cli
from src.evo.collect import ingest_dicts, read_cloud_usage_events, seed_demo_events
from src.evo.pipeline import generate_report
from src.evo.sanitize import REDACTED, sanitize_text, sanitize_value
from src.evo.store import EvoEvent, EvoStore
from src.main import cli


class FakeOllama:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict[str, str]] = []

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        self.calls.append({"prompt": prompt, "model": model, "system": system})
        return self.text


def test_sanitize_strips_secrets_from_text_and_payload() -> None:
    text = (
        "api_key=sk-abcdefghijklmnopqrstuvwxyz "
        "Bearer tokensecret123456789012 "
        "OPENROUTER_API_KEY=or-secret-value "
        "xai-abcdefghijklmnopqrstuvwxyz"
    )
    cleaned = sanitize_text(text)
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in cleaned
    assert "tokensecret123456789012" not in cleaned
    assert "or-secret-value" not in cleaned
    assert "xai-abcdefghijklmnopqrstuvwxyz" not in cleaned
    assert REDACTED in cleaned

    payload = sanitize_value(
        {
            "api_key": "sk-should-never-persist",
            "note": "token=abc123secretvaluehere",
            "nested": {"password": "hunter2"},
        }
    )
    assert payload["api_key"] == REDACTED
    assert payload["nested"]["password"] == REDACTED
    assert "abc123secretvaluehere" not in payload["note"]
    assert "hunter2" not in json.dumps(payload)


def test_store_persists_sanitized_and_fts(tmp_path: Path) -> None:
    db = tmp_path / "evo.sqlite3"
    with EvoStore(db) as store:
        eid = store.add_event(
            EvoEvent(
                kind="error",
                summary="fail with api_key=sk-abcdefghijklmnopqrstuvwxyz",
                source="test",
                payload={"api_key": "sk-abcdefghijklmnopqrstuvwxyz", "msg": "boom"},
                severity="error",
                ts="2026-11-18T12:00:00+00:00",
            )
        )
        assert eid >= 1
        rows = store.events_for_day("2026-11-18")
        assert len(rows) == 1
        assert "sk-abcdefghijklmnopqrstuvwxyz" not in rows[0]["summary"]
        assert rows[0]["payload"]["api_key"] == REDACTED
        hits = store.search("boom", day="2026-11-18")
        assert len(hits) == 1


def test_cloud_log_reader_redacts_and_never_requires_network(tmp_path: Path) -> None:
    log = tmp_path / "cloud_usage.jsonl"
    log.write_text(
        json.dumps(
            {
                "timestamp": 1_700_000_000.0,
                "provider": "openrouter",
                "model": "openrouter/free",
                "purpose": "ask",
                "input_tokens_estimate": 10,
                "output_tokens_estimate": 0,
                "result": "cloud_cancelled",
                "api_key": "should-be-stripped-by-reader",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    events = read_cloud_usage_events(log)
    assert len(events) == 1
    assert events[0].kind == "cloud_call"
    assert events[0].payload.get("api_key") == REDACTED


def test_aggregate_and_report_with_mocked_ollama(tmp_path: Path) -> None:
    day = "2026-11-18"
    db = tmp_path / "evo.sqlite3"
    out = tmp_path / "reports"
    fake = FakeOllama(
        json.dumps(
            {
                "hypotheses": [
                    {
                        "title": "Ollama flaky",
                        "rationale": "error events",
                        "confidence": 0.7,
                    }
                ],
                "proposals": [
                    {
                        "title": "Check hub",
                        "priority": 1,
                        "rationale": "local first",
                    }
                ],
                "risks": ["heuristic if model wrong"],
                "next_steps": ["re-run report"],
            }
        )
    )
    with EvoStore(db) as store:
        ingest_dicts(store, seed_demo_events(day))

    bundle = generate_report(
        day,
        db_path=db,
        reports_dir=out,
        completer=fake,
        model="fake-model",
        seed_demo=False,
        ingest_cloud=False,
    )
    assert bundle.path.is_file()
    md = bundle.markdown
    assert "## Day summary" in md
    assert "## Problems" in md
    assert "## Evidence" in md
    assert "## Hypotheses" in md
    assert "## Prioritized proposals" in md
    assert "## Risks" in md
    assert "## Next steps" in md
    assert "Ollama flaky" in md
    assert "sk-should-never-persist" not in md
    # Payload secret from seed must not survive store → report path
    stored = Path(db).read_bytes()
    assert b"sk-should-never-persist" not in stored
    assert len(fake.calls) == 1
    assert "cloud calls" in fake.calls[0]["system"].casefold()
    assert bundle.analysis.offline_fallback is False
    assert bundle.aggregate.total == 7
    assert bundle.cycle_state == "completed"


def test_analyze_falls_back_when_ollama_raises() -> None:
    class Boom:
        def complete(self, prompt: str, *, model: str, system: str) -> str:
            raise RuntimeError("down")

    agg = aggregate_day(
        "2026-11-18",
        [
            {
                "kind": "error",
                "summary": "Ollama indisponível",
                "severity": "error",
                "ts": "2026-11-18T12:00:00+00:00",
                "source": "engine",
                "payload": {},
            }
        ],
    )
    result = analyze_day(agg, completer=Boom(), model="x")
    assert result.offline_fallback is True
    assert result.hypotheses


def test_cli_report_seed_demo(tmp_path: Path) -> None:
    runner = CliRunner()
    db = tmp_path / "evo.sqlite3"
    out = tmp_path / "reports"
    result = runner.invoke(
        evo_cli,
        [
            "report",
            "--day",
            "2026-11-18",
            "--db",
            str(db),
            "--out",
            str(out),
            "--seed-demo",
            "--no-cloud-log",
            "--no-ollama",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "report:" in result.output
    report = out / "evo-2026-11-18.md"
    assert report.is_file()
    body = report.read_text(encoding="utf-8")
    assert "Day summary" in body
    assert "sk-should-never-persist" not in body


def test_main_cli_wires_evo_group() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["evo", "--help"])
    assert result.exit_code == 0
    assert "report" in result.output
