"""Lote 18: adaptador Cursor fake — dry-run de plano validated; sem MCP."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from src.brief.interview import answer_field, start_brief, try_propose
from src.cursor_fake.adapter import CursorFakeError, format_report, simulate
from src.main import cli
from src.plan.builder import build_plan_from_brief
from src.plan.schemas import PlanStep, YbyPlan
from src.plan.store import PlanStore


def _ready_brief(idea: str = "CLI de anotações offline"):
    brief, _ = start_brief(idea)
    for key, text in (
        ("objective", "anotar ideias offline"),
        ("audience", "dev"),
        ("scope", "CLI local markdown"),
        ("out_of_scope", "app mobile e sync nuvem"),
        ("constraints", "sem rede"),
        ("required_data", "pasta de notas"),
        ("acceptance", "criar e listar notas"),
        ("risks", "perder arquivo local"),
    ):
        answer_field(brief, key, text)
    try_propose(brief)
    return brief


def test_simulate_validated_nao_executa() -> None:
    plan = build_plan_from_brief(_ready_brief())
    assert plan.status == "validated"
    report = simulate(plan)
    assert report.plan_id == plan.id
    assert report.plan_version == plan.version
    assert report.adapter == "cursor_fake"
    assert "sem MCP" in report.warning
    assert len(report.steps) == len(plan.steps)
    assert all(step.executed is False for step in report.steps)
    assert all(step.action == "skip_no_mcp" for step in report.steps)
    text = format_report(report)
    assert "executed=False" in text
    assert plan.id in text


def test_simulate_draft_rejeita() -> None:
    plan = YbyPlan(
        id="draft1",
        brief_id="b1",
        status="draft",
        steps=[
            PlanStep(
                id="s1",
                order=1,
                kind="read",
                objective="ler escopo",
                files=["README.md"],
                allowed_commands=["ls"],
                tests=["n/a"],
                acceptance="ok",
                revert="nada",
            )
        ],
    )
    with pytest.raises(CursorFakeError, match="validated"):
        simulate(plan)


def test_simulate_rejected_rejeita() -> None:
    plan = YbyPlan(id="rej1", brief_id="b1", status="rejected", steps=[])
    with pytest.raises(CursorFakeError, match="validated"):
        simulate(plan)


def test_cli_simulate_happy_and_reject(tmp_path: Path) -> None:
    plan = build_plan_from_brief(_ready_brief())
    store = PlanStore(tmp_path / "plans")
    store.save(plan)

    runner = CliRunner()
    ok = runner.invoke(
        cli, ["cursor-fake", "simulate", plan.id, "--dir", str(store.root)]
    )
    assert ok.exit_code == 0, ok.output
    assert "cursor_fake" in ok.output
    assert "skip_no_mcp" in ok.output
    assert "executed=False" in ok.output

    as_json = runner.invoke(
        cli,
        ["cursor-fake", "simulate", plan.id, "--dir", str(store.root), "--json"],
    )
    assert as_json.exit_code == 0, as_json.output
    assert '"adapter": "cursor_fake"' in as_json.output
    assert '"executed": false' in as_json.output

    draft = YbyPlan(id="d2", brief_id="b", status="draft", steps=[])
    store.save(draft)
    bad = runner.invoke(
        cli, ["cursor-fake", "simulate", "d2", "--dir", str(store.root)]
    )
    assert bad.exit_code == 1
    assert "validated" in bad.output.lower() or "validated" in str(bad.exception)

    missing = runner.invoke(
        cli, ["cursor-fake", "simulate", "nope", "--dir", str(store.root)]
    )
    assert missing.exit_code == 1
