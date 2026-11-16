"""Gerador controlado de artefatos. Sem install/deploy automático."""

from src.artifacts.generator import (
    ArtifactError,
    apply_manifest,
    propose_scaffold,
    revert_applied,
)
from src.artifacts.manifest import ArtifactManifest

__all__ = [
    "ArtifactError",
    "ArtifactManifest",
    "apply_manifest",
    "propose_scaffold",
    "revert_applied",
]
