"""Valida plano contra brief e allowlist. Modelo não é autoridade de segurança."""

from __future__ import annotations

from pathlib import Path

from src.brief.schemas import YbyBrief
from src.plan.schemas import PlanStep, YbyPlan
from src.safety.policy import Policy, decide, default_policy_path, load_policy


def validate_plan(
    plan: YbyPlan,
    brief: YbyBrief,
    *,
    policy: Policy | None = None,
    project_root: Path | None = None,
) -> list[str]:
    """Devolve motivos de rejeição (vazio = ok). Não executa comandos."""

    reasons: list[str] = []
    if brief.status not in {"ready", "proposed"}:
        reasons.append("brief incompleto ou não pronto — plano não gerado")
        return reasons
    if plan.brief_id != brief.id:
        reasons.append("plan.brief_id diverge do brief")
    if not plan.steps:
        reasons.append("plano sem etapas")

    policy = policy or load_policy(default_policy_path())
    root = project_root or default_policy_path().parents[1]
    brief_scope = (brief.scope or "").casefold()
    brief_out = (brief.out_of_scope or "").casefold()
    seen_ids: set[str] = set()

    for step in sorted(plan.steps, key=lambda s: s.order):
        reasons.extend(_validate_step(step, brief_scope, brief_out, seen_ids, policy, root))
        seen_ids.add(step.id)

    for step in plan.steps:
        for dep in step.depends_on:
            if dep not in seen_ids:
                reasons.append(f"etapa {step.id}: dependência inexistente {dep}")

    return reasons


def _validate_step(
    step: PlanStep,
    brief_scope: str,
    brief_out: str,
    seen_ids: set[str],
    policy: Policy,
    root: Path,
) -> list[str]:
    reasons: list[str] = []
    if step.id in seen_ids:
        reasons.append(f"id de etapa duplicado: {step.id}")
    if not step.acceptance.strip():
        reasons.append(f"etapa {step.id}: critério de aceite vazio")
    if not step.revert.strip():
        reasons.append(f"etapa {step.id}: reversão vazia")

    blob = " ".join(
        [step.objective, *step.files, *step.tests, step.acceptance]
    ).casefold()
    if brief_out and any(
        token and token in blob for token in _tokens(brief_out) if len(token) > 3
    ):
        # Só rejeita se o fora-de-escopo aparece como intenção clara na etapa.
        for token in _tokens(brief_out):
            if len(token) > 4 and token in blob:
                reasons.append(
                    f"etapa {step.id}: fora do escopo do brief ({token})"
                )
                break

    if brief_scope and step.kind == "create":
        # create deve mencionar algo alinhado ao escopo (heurística leve).
        scope_tokens = [t for t in _tokens(brief_scope) if len(t) > 3]
        if scope_tokens and not any(t in blob for t in scope_tokens):
            reasons.append(
                f"etapa {step.id}: create sem ligação explícita ao escopo do brief"
            )

    for command in step.allowed_commands:
        decision = decide(command, policy=policy, project_root=root)
        if decision.action == "refuse":
            reasons.append(
                f"etapa {step.id}: comando não autorizado ({command}): {decision.reason}"
            )
        # ask/run são permitidos no plano; execução exige autorização própria.
        if step.authorized and decision.action != "run":
            reasons.append(
                f"etapa {step.id}: authorized=true só com comando `run` "
                f"(obtido {decision.action} para {command!r})"
            )

    return reasons


def _tokens(text: str) -> list[str]:
    return [part for part in "".join(
        ch.lower() if ch.isalnum() else " " for ch in text
    ).split() if part]
