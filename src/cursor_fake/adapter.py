"""Adaptador Cursor fake: dry-run de plano validated; sem MCP / disco / rede."""

from __future__ import annotations

from src.cursor_fake.schemas import DryRunReport, SimulatedStep
from src.plan.schemas import YbyPlan


class CursorFakeError(ValueError):
    """Plano inadequado para o adaptador fake."""


def simulate(plan: YbyPlan) -> DryRunReport:
    """Simula o que um Cursor faria com o plano — só relatório, zero side effects."""

    if plan.status != "validated":
        raise CursorFakeError(
            f"plano status={plan.status!r} (exige validated). "
            "Use `yby plan from-brief` ou `yby plan validate` antes."
        )

    steps: list[SimulatedStep] = []
    cited: list[str] = []
    seen: set[str] = set()
    for step in sorted(plan.steps, key=lambda item: item.order):
        steps.append(
            SimulatedStep(
                id=step.id,
                order=step.order,
                kind=step.kind,
                objective=step.objective,
                files=list(step.files),
                allowed_commands=list(step.allowed_commands),
                tests=list(step.tests),
                action="skip_no_mcp",
                executed=False,
            )
        )
        for path in step.files:
            if path not in seen:
                seen.add(path)
                cited.append(path)

    return DryRunReport(
        plan_id=plan.id,
        plan_version=plan.version,
        brief_id=plan.brief_id,
        plan_status=plan.status,
        steps=steps,
        cited_files=cited,
    )


def format_report(report: DryRunReport) -> str:
    """Texto legível para CLI (alternativa a --json)."""

    lines = [
        f"adapter: {report.adapter}",
        f"plan: {report.plan_id} v{report.plan_version} ({report.plan_status})",
        f"brief: {report.brief_id}",
        f"aviso: {report.warning}",
        f"arquivos citados: {', '.join(report.cited_files) or '(nenhum)'}",
        f"etapas: {len(report.steps)}",
    ]
    for step in report.steps:
        lines.append(
            f"  [{step.order}] {step.id} {step.kind}: {step.objective} "
            f"→ {step.action} executed={step.executed}"
        )
    return "\n".join(lines)
