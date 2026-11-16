"""Monta e revisa planos a partir de brief pronto. Não executa."""

from __future__ import annotations

import secrets
from pathlib import Path

from src.brief.interview import missing_fields
from src.brief.schemas import YbyBrief
from src.plan.schemas import PlanStep, YbyPlan
from src.plan.validate import validate_plan
from src.safety.policy import Policy


class PlanError(ValueError):
    """Falha ao construir ou validar plano."""


def build_plan_from_brief(
    brief: YbyBrief,
    *,
    policy: Policy | None = None,
    project_root: Path | None = None,
) -> YbyPlan:
    """Gera plano mínimo (read→analyze→create→test→deliver). Sem execução."""

    if missing_fields(brief) or brief.status not in {"ready", "proposed"}:
        raise PlanError("brief incompleto — plano não gerado")

    plan = YbyPlan(
        id=_new_id(),
        brief_id=brief.id,
        version=1,
        steps=_default_steps(brief),
    )
    reasons = validate_plan(plan, brief, policy=policy, project_root=project_root)
    if reasons:
        plan.status = "rejected"
        plan.rejection_reasons = reasons
        raise PlanError("; ".join(reasons))
    plan.status = "validated"
    plan.rejection_reasons = []
    plan.touch()
    return plan


def revise_plan(
    plan: YbyPlan,
    brief: YbyBrief,
    *,
    steps: list[PlanStep] | None = None,
    policy: Policy | None = None,
    project_root: Path | None = None,
) -> YbyPlan:
    """Nova versão do plano; valida de novo contra o brief."""

    if plan.brief_id != brief.id:
        raise PlanError("não é possível revisar plano com brief diferente")
    updated = plan.model_copy(deep=True)
    updated.version = plan.version + 1
    if steps is not None:
        updated.steps = steps
    # Revisão não herda authorized — cada etapa precisa de nova autorização.
    for step in updated.steps:
        step.authorized = False
    reasons = validate_plan(updated, brief, policy=policy, project_root=project_root)
    if reasons:
        updated.status = "rejected"
        updated.rejection_reasons = reasons
        raise PlanError("; ".join(reasons))
    updated.status = "validated"
    updated.rejection_reasons = []
    updated.touch()
    return updated


def _default_steps(brief: YbyBrief) -> list[PlanStep]:
    scope = brief.scope or "escopo do brief"
    return [
        PlanStep(
            id="s1",
            order=1,
            kind="read",
            objective=f"Ler contexto local relevante a: {brief.objective}",
            files=["ROADMAP.md", "docs/DEV.md"],
            allowed_commands=["ls", "git status"],
            tests=["listagem do vault/repo não falha"],
            acceptance="Arquivos de contexto identificados",
            revert="nada a desfazer (somente leitura)",
            risks=["ler path sensível fora do vault"],
        ),
        PlanStep(
            id="s2",
            order=2,
            kind="analyze",
            objective=f"Analisar restrições: {brief.constraints}",
            files=[],
            allowed_commands=[],
            tests=["checklist de restrições documentado"],
            acceptance="Riscos e restrições listados sem executar shell",
            revert="descartar anotações da análise",
            depends_on=["s1"],
            risks=["assumir requisito não dito"],
        ),
        PlanStep(
            id="s3",
            order=3,
            kind="create",
            objective=f"Propor artefatos no escopo: {scope}",
            files=["src/"],
            allowed_commands=[],
            tests=["nenhum arquivo criado neste lote (só plano)"],
            acceptance="Lista de arquivos alvo alinhada ao escopo",
            revert="não criar arquivos até autorização",
            depends_on=["s2"],
            risks=["expandir escopo sem novo brief"],
        ),
        PlanStep(
            id="s4",
            order=4,
            kind="test",
            objective="Definir testes verificáveis do aceite do brief",
            files=["tests/"],
            allowed_commands=[],
            tests=[brief.acceptance or "critério do brief"],
            acceptance="Cada teste mapeia a um critério de aceite",
            revert="remover rascunho de testes não commitados",
            depends_on=["s3"],
            risks=["teste que exige rede sem consentimento"],
        ),
        PlanStep(
            id="s5",
            order=5,
            kind="deliver",
            objective="Entregar só após aprovação humana explícita",
            files=[],
            allowed_commands=[],
            tests=["checklist de revisão preenchido"],
            acceptance="Humano aprovou; nenhuma etapa ficou authorized sem gate",
            revert="não publicar / reverter commits se já feitos fora deste módulo",
            depends_on=["s4"],
            risks=["tratar plano como autorização de execução"],
        ),
    ]


def _new_id() -> str:
    return secrets.token_hex(4)
