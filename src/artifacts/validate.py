"""Validação estática de artefatos. Sem sandbox OS → execução bloqueada."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from src.engine.secret_gate import find_secret

_FORBIDDEN_CALL = re.compile(
    r"\b(eval|exec|compile|__import__)\s*\(",
    re.IGNORECASE,
)

# Sem isolamento de SO no v1: nunca executar código gerado automaticamente.
OS_SANDBOX_AVAILABLE = False


@dataclass
class ValidationIssue:
    path: str
    message: str
    next_step: str


@dataclass
class ValidationReport:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    partial_failures: list[str] = field(default_factory=list)

    def raise_if_failed(self) -> None:
        if self.ok:
            return
        from src.artifacts.generator import ArtifactError

        lines = [f"{i.path}: {i.message} → {i.next_step}" for i in self.issues]
        lines.extend(f"parcial: {p}" for p in self.partial_failures)
        raise ArtifactError("validação falhou:\n" + "\n".join(lines))


def validate_contents(contents: dict[str, str]) -> ValidationReport:
    """Sintaxe/estrutura antes de aplicar. Não executa o código."""

    issues: list[ValidationIssue] = []
    partial: list[str] = []
    py_files = [p for p in contents if p.endswith(".py")]
    tests = [p for p in contents if p.startswith("tests/") and p.endswith(".py")]

    if not py_files:
        issues.append(
            ValidationIssue(
                path="(projeto)",
                message="nenhum arquivo .py",
                next_step="inclua pacote Python mínimo antes de aplicar",
            )
        )
    if not tests:
        issues.append(
            ValidationIssue(
                path="tests/",
                message="código sem teste não é aceito como pronto",
                next_step="adicione tests/test_*.py com asserção",
            )
        )
    if "README.md" not in contents:
        issues.append(
            ValidationIssue(
                path="README.md",
                message="README ausente",
                next_step="gere README.md descrevendo uso local",
            )
        )

    for path, body in sorted(contents.items()):
        if find_secret(body) is not None:
            issues.append(
                ValidationIssue(
                    path=path,
                    message="segredo detectado no artefato",
                    next_step="remova credenciais e regenere a proposta",
                )
            )
        if not path.endswith(".py"):
            continue
        try:
            ast.parse(body)
        except SyntaxError as exc:
            issues.append(
                ValidationIssue(
                    path=path,
                    message=f"sintaxe inválida: {exc.msg} (linha {exc.lineno})",
                    next_step="corrija o arquivo e rode scaffold validate de novo",
                )
            )
            continue
        if _FORBIDDEN_CALL.search(body):
            issues.append(
                ValidationIssue(
                    path=path,
                    message="uso de eval/exec/compile/__import__ bloqueado",
                    next_step="reescreva sem metaprogramação dinâmica",
                )
            )

    report = ValidationReport(ok=not issues, issues=issues, partial_failures=partial)
    return report


def assert_execution_blocked(reason: str = "código gerado") -> None:
    """Bloqueia execução: sem sandbox OS (Lote 17 / D10)."""

    from src.artifacts.generator import ArtifactError

    if OS_SANDBOX_AVAILABLE:
        return
    raise ArtifactError(
        f"execução de {reason} bloqueada: sem isolamento de SO no v1 "
        "(documentado). Rode testes só em ambiente humano/revisado; "
        "não há auto-retry com efeito colateral."
    )


def format_report(report: ValidationReport) -> str:
    if report.ok:
        return "validação: ok (estática; execução de código gerado continua bloqueada)"
    lines = ["validação: falhou"]
    for issue in report.issues:
        lines.append(f"- {issue.path}: {issue.message}")
        lines.append(f"  próximo: {issue.next_step}")
    for partial in report.partial_failures:
        lines.append(f"- falha parcial (não ocultada): {partial}")
    return "\n".join(lines)
