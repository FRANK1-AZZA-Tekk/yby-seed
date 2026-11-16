"""Manifesto de artefatos: hashes e origem. Proposta até aprovação."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class ArtifactFile(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    sha256: str = Field(min_length=64, max_length=64)
    bytes: int = Field(ge=0)
    origin: str = Field(min_length=1, max_length=200)


class ArtifactManifest(BaseModel):
    schema_version: Literal["yby-artifacts/v1"] = "yby-artifacts/v1"
    plan_id: str = Field(min_length=1, max_length=64)
    target_dir: str = Field(min_length=1)
    status: Literal["proposed", "applied", "reverted"] = "proposed"
    stack: Literal["python-cli"] = "python-cli"
    files: list[ArtifactFile] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: _now())

    def file_paths(self) -> list[str]:
        return [f.path for f in self.files]


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
