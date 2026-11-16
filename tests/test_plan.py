"""Lote 15: plano verificável — validação vs brief/allowlist; sem execução."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from src.brief.interview import answer_field, start_brief, try_propose
from src.brief.store import BriefStore
from src.main import cli
from src.plan.builder import PlanError, build_plan_from_brief, revise_plan
from src.plan.schemas import PlanStep, YbyPlan
from src.plan.store import PlanStore
from src.plan.validate import validate_plan


def _ready_brief(idea: str = "ferramenta CLI de flashcards offline"):
    brief, _ = start_brief(idea)
    for key, text in (
        ("objective", "revisar vocabulário offline"),
        ("audience", "estudante"),
        ("scope", "CLI local com cartões markdown"),
        ("out_of_scope", "aplicativo mobile e sync nuvem"),
        ("constraints", "sem rede"),
        ("required_data", "lista de palavras"),
        ("acceptance", "revisar 10 cartões sem internet"),
        ("risks", "perder arquivo local"),
    ):
        answer_field(brief, key, text)
    try_propose(brief)
    return brief


def test_brief_incompleto_nao_gera_plano() -> None:
    brief, _ = start_brief("ideia incompleta para testar")
    with pytest.raises(PlanError, match="incompleto"):
        build_plan_from_brief(brief)


def test_etapa_fora_do_escopo_rejeitada() -> None:
    brief = _ready_brief()
    plan = YbyPlan(
        id="p1",
        brief_id=brief.id,
        steps=[
            PlanStep(
                id="bad",
                order=1,
                kind="create",
                objective="publicar aplicativo mobile na loja",
                files=["mobile/"],
                allowed_commands=[],
                tests=["build mobile"],
                acceptance="app na store",
                revert="remover app",
            )
        ],
    )
    reasons = validate_plan(plan, brief)
    assert any("fora do escopo" in r for r in reasons)


def test_comando_nao_autorizado_rejeitado() -> None:
    brief = _ready_brief()
    plan = YbyPlan(
        id="p2",
        brief_id=brief.id,
        steps=[
            PlanStep(
                id="s1",
                order=1,
                kind="read",
                objective="ler arquivos do escopo CLI local",
                files=["src/"],
                allowed_commands=["rm -rf /"],
                tests=["n/a"],
                acceptance="não deve passar",
                revert="nada",
            )
        ],
    )
    reasons = validate_plan(plan, brief)
    assert any("não autorizado" in r for r in reasons)


def test_plano_pode_ser_revisado_e_versionado(tmp_path: Path) -> None:
    brief = _ready_brief()
    plan = build_plan_from_brief(brief)
    assert plan.status == "validated"
    assert plan.version == 1
    assert all(s.acceptance for s in plan.steps)

    trimmed = [s for s in plan.steps if s.id != "s5"]
    # deliver depende de s4; manter s1-s4
    updated = revise_plan(plan, brief, steps=trimmed)
    assert updated.version == 2
    assert updated.status == "validated"
    assert all(not s.authorized for s in updated.steps)

    store = PlanStore(tmp_path)
    store.save(plan)
    store.save(updated)
    assert store.load(plan.id).version == 2
    assert store.load(plan.id, version=1).version == 1


def test_cada_etapa_tem_criterio_verificavel() -> None:
    brief = _ready_brief()
    plan = build_plan_from_brief(brief)
    for step in plan.steps:
        assert step.acceptance.strip()
        assert step.revert.strip()
        assert step.kind in {"read", "analyze", "create", "test", "deliver"}


def test_cli_plan_from_brief(tmp_path: Path) -> None:
    briefs = tmp_path / "briefs"
    plans = tmp_path / "plans"
    brief = _ready_brief()
    BriefStore(briefs).save(brief)

    runner = CliRunner()
    blocked = runner.invoke(
        cli,
        [
            "plan",
            "from-brief",
            "missing",
            "--brief-dir",
            str(briefs),
            "--dir",
            str(plans),
        ],
    )
    assert blocked.exit_code == 1

    incomplete, _ = start_brief("ainda sem campos suficientes aqui")
    BriefStore(briefs).save(incomplete)
    no_plan = runner.invoke(
        cli,
        [
            "plan",
            "from-brief",
            incomplete.id,
            "--brief-dir",
            str(briefs),
            "--dir",
            str(plans),
        ],
    )
    assert no_plan.exit_code == 1
    assert "incompleto" in no_plan.output

    ok = runner.invoke(
        cli,
        [
            "plan",
            "from-brief",
            brief.id,
            "--brief-dir",
            str(briefs),
            "--dir",
            str(plans),
        ],
    )
    assert ok.exit_code == 0, ok.output
    assert "validated" in ok.output
    assert "yby-plan/v1" in ok.output
