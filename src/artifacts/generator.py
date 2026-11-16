"""Propõe e aplica scaffolds. Sem install/deploy."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from src.artifacts.manifest import ArtifactFile, ArtifactManifest, sha256_text
from src.artifacts.templates import python_cli_files
from src.engine.secret_gate import find_secret
from src.plan.schemas import YbyPlan


class ArtifactError(ValueError):
    """Falha ao propor ou aplicar artefatos."""


def propose_scaffold(
    plan: YbyPlan,
    target_dir: Path,
    *,
    name: str,
    objective: str,
) -> tuple[ArtifactManifest, dict[str, str]]:
    """Gera manifesto + conteúdos em memória. Não escreve disco (exceto checks)."""

    if plan.status != "validated":
        raise ArtifactError("plano precisa estar validated")
    target = target_dir.expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        raise ArtifactError(
            f"diretório existente não vazio não é sobrescrito: {target}"
        )
    contents = python_cli_files(name=name, objective=objective)
    files: list[ArtifactFile] = []
    for rel, body in sorted(contents.items()):
        if find_secret(body) is not None:
            raise ArtifactError(f"saída inválida: segredo em {rel}")
        files.append(
            ArtifactFile(
                path=rel,
                sha256=sha256_text(body),
                bytes=len(body.encode("utf-8")),
                origin=f"template:python-cli@plan:{plan.id}",
            )
        )
    manifest = ArtifactManifest(
        plan_id=plan.id,
        target_dir=str(target),
        status="proposed",
        files=files,
    )
    return manifest, contents


def apply_manifest(
    manifest: ArtifactManifest,
    contents: dict[str, str],
    *,
    approve_overwrite: bool = False,
) -> ArtifactManifest:
    """Escreve arquivos. Nunca sobrescreve existente sem `approve_overwrite`."""

    if manifest.status != "proposed":
        raise ArtifactError("só proposta pode ser aplicada")
    root = Path(manifest.target_dir)
    root.mkdir(parents=True, exist_ok=True)

    for meta in manifest.files:
        rel = meta.path
        if rel not in contents:
            raise ArtifactError(f"saída inválida: falta conteúdo de {rel}")
        body = contents[rel]
        if sha256_text(body) != meta.sha256:
            raise ArtifactError(f"saída inválida: hash divergente em {rel}")
        if find_secret(body) is not None:
            raise ArtifactError(f"segredo não pode aparecer em artefato: {rel}")
        dest = (root / rel).resolve()
        try:
            dest.relative_to(root.resolve())
        except ValueError as exc:
            raise ArtifactError(f"path fora do alvo: {rel}") from exc
        if dest.exists() and not approve_overwrite:
            raise ArtifactError(f"arquivo existente não substituído: {rel}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")

    manifest_path = root / ".yby" / "artifacts-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    applied = manifest.model_copy(update={"status": "applied"})
    manifest_path.write_text(
        json.dumps(applied.model_dump(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return applied


def revert_applied(manifest: ArtifactManifest) -> ArtifactManifest:
    """Remove arquivos listados e o manifesto. Diretório alvo pode sobrar vazio."""

    if manifest.status != "applied":
        raise ArtifactError("só artefato applied pode ser revertido")
    root = Path(manifest.target_dir)
    for meta in manifest.files:
        path = root / meta.path
        if path.is_file():
            path.unlink()
    man = root / ".yby" / "artifacts-manifest.json"
    if man.is_file():
        man.unlink()
    # limpa dirs vazios de baixo para cima
    for meta in sorted(manifest.files, key=lambda f: f.path, reverse=True):
        parent = (root / meta.path).parent
        while parent != root and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    yby = root / ".yby"
    if yby.is_dir() and not any(yby.iterdir()):
        yby.rmdir()
    if root.is_dir() and not any(root.iterdir()):
        root.rmdir()
    return manifest.model_copy(update={"status": "reverted"})


def remove_target_tree(target: Path) -> None:
    """Remove árvore inteira (só para testes / revert agressivo)."""

    if target.exists():
        shutil.rmtree(target)
