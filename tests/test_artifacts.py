"""Lote 16: gerador de artefatos controlado — sem install/deploy."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.artifacts.generator import (
    ArtifactError,
    apply_manifest,
    propose_scaffold,
    revert_applied,
)
from src.artifacts.templates import python_cli_files
from src.brief.interview import answer_field, start_brief, try_propose
from src.plan.builder import build_plan_from_brief
from src.plan.schemas import YbyPlan


def _validated_plan() -> YbyPlan:
    brief, _ = start_brief("CLI de notas offline")
    for key, text in (
        ("objective", "anotar ideias localmente"),
        ("audience", "eu"),
        ("scope", "CLI python local"),
        ("out_of_scope", "site react e deploy"),
        ("constraints", "sem rede"),
        ("required_data", "textos curtos"),
        ("acceptance", "comando --help funciona"),
        ("risks", "sobrescrever pasta"),
    ):
        answer_field(brief, key, text)
    try_propose(brief)
    return build_plan_from_brief(brief)


def test_diretorio_existente_nao_sobrescrito(tmp_path: Path) -> None:
    plan = _validated_plan()
    target = tmp_path / "app"
    target.mkdir()
    (target / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ArtifactError, match="não é sobrescrito|não vazio"):
        propose_scaffold(plan, target, name="notas", objective="x")


def test_arquivo_existente_nao_substituido_sem_aprovacao(tmp_path: Path) -> None:
    plan = _validated_plan()
    target = tmp_path / "fresh"
    manifest, contents = propose_scaffold(
        plan, target, name="notas", objective="anotar"
    )
    target.mkdir()
    first = next(iter(contents))
    (target / first).parent.mkdir(parents=True, exist_ok=True)
    (target / first).write_text("ocupado", encoding="utf-8")
    with pytest.raises(ArtifactError, match="não substituído"):
        apply_manifest(manifest, contents, approve_overwrite=False)


def test_saida_invalida_hash_rejeitada(tmp_path: Path) -> None:
    plan = _validated_plan()
    target = tmp_path / "app2"
    manifest, contents = propose_scaffold(
        plan, target, name="notas", objective="anotar"
    )
    contents[next(iter(contents))] = "conteudo adulterado"
    with pytest.raises(ArtifactError, match="hash|inválida"):
        apply_manifest(manifest, contents)


def test_segredo_nao_aparece_em_artefato() -> None:
    files = python_cli_files(name="safe_app", objective="sem segredo")
    blob = "\n".join(files.values())
    assert "sk-" not in blob
    assert "API_KEY" not in blob


def test_artefato_pode_ser_revertido(tmp_path: Path) -> None:
    plan = _validated_plan()
    target = tmp_path / "rev"
    manifest, contents = propose_scaffold(
        plan, target, name="revapp", objective="teste revert"
    )
    applied = apply_manifest(manifest, contents)
    assert (target / "README.md").is_file()
    revert_applied(applied)
    assert not target.exists() or not (target / "README.md").exists()


def test_apply_happy_path(tmp_path: Path) -> None:
    plan = _validated_plan()
    target = tmp_path / "ok"
    manifest, contents = propose_scaffold(
        plan, target, name="okapp", objective="scaffold ok"
    )
    assert manifest.status == "proposed"
    applied = apply_manifest(manifest, contents)
    assert applied.status == "applied"
    assert (target / ".yby" / "artifacts-manifest.json").is_file()
    assert (target / "okapp" / "main.py").is_file()
