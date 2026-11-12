"""Fluxo exocórtex: intenção → skill → dry-run → confirmação → ação → ledger."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from src.actions.runner import run_command
from src.orchestration.ledger import append_ledger_event, new_decision_id
from src.safety.policy import default_policy_path, load_policy
from src.security.ast_guard import validate_code_ast
from src.skills.skill_manager import Skill, SkillManager

Mode = Literal["skill", "conversation"]


@dataclass(frozen=True)
class ExocortexOutcome:
    decision_id: str
    mode: Mode
    skill_name: str | None
    dry_run: str
    approved: bool
    executed: bool
    stdout: str
    stderr: str
    recorded: bool


def propose_shell_command(intent: str, skill: Skill | None) -> str | None:
    """Heurística mínima: mapeia intenção + skill a comando allowlisted."""
    if skill is None:
        return None
    lowered = intent.casefold()
    if skill.metadata.name == "file-operations":
        if any(w in lowered for w in ("listar", "lista", "ls", "diretório", "diretorio", "pasta")):
            return "ls"
        if any(w in lowered for w in ("espaço", "espaco", "disco", "df")):
            return "df -h"
    return None


def _validate_skill_scripts(skill: Skill) -> list[str]:
    issues: list[str] = []
    for script in skill.get_scripts():
        ok, problems = validate_code_ast(script.read_text(encoding="utf-8"))
        if not ok:
            issues.append(f"{script.name}: {'; '.join(problems)}")
    return issues


def run_exocortex(
    intent: str,
    *,
    auto_yes: bool = False,
    skills_dir: Path | None = None,
    project_root: Path | None = None,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], None],
    record_vault_fn: Callable[[str, str], None] | None = None,
) -> ExocortexOutcome:
    root = project_root or default_policy_path().parents[1]
    skills_path = skills_dir or (root / "skills")
    decision_id = new_decision_id()

    manager = SkillManager(skills_dir=str(skills_path))
    manager.discover_skills()
    skill = manager.find_best_skill(intent)
    if skill is None:
        return ExocortexOutcome(
            decision_id=decision_id,
            mode="conversation",
            skill_name=None,
            dry_run="",
            approved=False,
            executed=False,
            stdout="",
            stderr="",
            recorded=False,
        )

    script_issues = _validate_skill_scripts(skill)
    if script_issues:
        output_fn("skill com scripts bloqueados pelo AST guard:")
        for issue in script_issues:
            output_fn(f"  - {issue}")

    proposed = propose_shell_command(intent, skill)
    dry_run = (
        f"Skill: {skill.metadata.name}\n"
        f"Descrição: {skill.metadata.description[:200]}\n"
        f"Ação proposta: {proposed or '(somente registro no vault/ledger)'}"
    )
    output_fn("--- dry-run ---")
    output_fn(dry_run)

    if not auto_yes:
        answer = input_fn().strip().casefold()
        if answer not in {"s", "sim", "y", "yes"}:
            append_ledger_event(
                {
                    "decision_id": decision_id,
                    "intent": intent,
                    "skill": skill.metadata.name,
                    "status": "cancelled",
                    "proposed_command": proposed,
                }
            )
            return ExocortexOutcome(
                decision_id=decision_id,
                mode="skill",
                skill_name=skill.metadata.name,
                dry_run=dry_run,
                approved=False,
                executed=False,
                stdout="",
                stderr="",
                recorded=True,
            )
    else:
        output_fn("(confirmação automática: --yes)")

    stdout = ""
    stderr = ""
    executed = False
    policy = load_policy(default_policy_path())

    if proposed:

        def _input() -> str:
            return "s" if auto_yes else input_fn()

        run_result = run_command(
            proposed,
            policy=policy,
            project_root=root,
            input_fn=_input,
            output_fn=output_fn,
        )
        executed = run_result.executed
        stdout = run_result.stdout
        stderr = run_result.stderr

    if record_vault_fn is not None:
        record_vault_fn(
            f"exocortex-{decision_id}",
            f"# Skill {skill.metadata.name}\n\nIntenção: {intent}\n\nComando: {proposed or 'n/a'}\n",
        )

    append_ledger_event(
        {
            "decision_id": decision_id,
            "intent": intent,
            "skill": skill.metadata.name,
            "status": "executed" if executed else "recorded",
            "proposed_command": proposed,
            "stdout_preview": stdout[:500],
        }
    )

    return ExocortexOutcome(
        decision_id=decision_id,
        mode="skill",
        skill_name=skill.metadata.name,
        dry_run=dry_run,
        approved=True,
        executed=executed,
        stdout=stdout,
        stderr=stderr,
        recorded=True,
    )
