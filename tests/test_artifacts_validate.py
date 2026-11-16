"""Lote 17: validação estática; execução de gerado bloqueada sem sandbox."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.artifacts.generator import ArtifactError, apply_manifest, propose_scaffold
from src.artifacts.templates import python_cli_files
from src.artifacts.validate import (
    OS_SANDBOX_AVAILABLE,
    assert_execution_blocked,
    validate_contents,
)
from src.brief.interview import answer_field, start_brief, try_propose
from src.plan.builder import build_plan_from_brief


def _plan():
    brief, _ = start_brief("validador de scaffold")
    for key, text in (
        ("objective", "validar artefatos"),
        ("audience", "dev"),
        ("scope", "CLI python"),
        ("out_of_scope", "sandbox completo"),
        ("constraints", "sem exec automático"),
        ("required_data", "arquivos gerados"),
        ("acceptance", "sintaxe ok e testes presentes"),
        ("risks", "executar código inseguro"),
    ):
        answer_field(brief, key, text)
    try_propose(brief)
    return build_plan_from_brief(brief)


def test_codigo_invalido_rejeitado() -> None:
    contents = python_cli_files(name="badapp", objective="x")
    contents["badapp/main.py"] = "def broken(\n"
    report = validate_contents(contents)
    assert not report.ok
    assert any("sintaxe" in i.message for i in report.issues)


def test_codigo_sem_teste_nao_pronto() -> None:
    contents = {
        "README.md": "x",
        "pkg/__init__.py": "",
        "pkg/main.py": "def main():\n    return 1\n",
    }
    report = validate_contents(contents)
    assert not report.ok
    assert any("sem teste" in i.message for i in report.issues)


def test_eval_bloqueado() -> None:
    contents = python_cli_files(name="evil", objective="x")
    contents["evil/main.py"] = "def main():\n    return eval('1')\n"
    report = validate_contents(contents)
    assert not report.ok
    assert any("eval" in i.message for i in report.issues)


def test_falha_validacao_nao_corrompe_projeto(tmp_path: Path) -> None:
    plan = _plan()
    target = tmp_path / "proj"
    manifest, contents = propose_scaffold(plan, target, name="proj", objective="ok")
    # aplica happy path parcial: alvo ainda vazio
    assert not target.exists()
    bad = dict(contents)
    bad["proj/main.py"] = "def broken(\n"
    from src.artifacts.manifest import ArtifactFile, sha256_text

    # alinha hash para chegar na validação de sintaxe (não no check de hash)
    files = []
    for meta in manifest.files:
        body = bad[meta.path]
        files.append(
            ArtifactFile(
                path=meta.path,
                sha256=sha256_text(body),
                bytes=len(body.encode("utf-8")),
                origin=meta.origin,
            )
        )
    broken_manifest = manifest.model_copy(update={"files": files})
    with pytest.raises(ArtifactError, match="validação falhou"):
        apply_manifest(broken_manifest, bad)
    assert not (target / "README.md").exists()


def test_execucao_gerada_bloqueada_sem_sandbox() -> None:
    assert OS_SANDBOX_AVAILABLE is False
    with pytest.raises(ArtifactError, match="bloqueada"):
        assert_execution_blocked("pytest")


def test_repeticao_nao_automatica(tmp_path: Path) -> None:
    """Falha não dispara retry com efeito colateral."""

    from src.artifacts.generator import run_generated_tests

    with pytest.raises(ArtifactError, match="bloqueada"):
        run_generated_tests(tmp_path)
    with pytest.raises(ArtifactError, match="bloqueada"):
        run_generated_tests(tmp_path)
