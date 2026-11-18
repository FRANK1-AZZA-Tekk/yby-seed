"""Raízes de leitura permitidas para ferramentas de arquivo."""

from __future__ import annotations

import os
from pathlib import Path


class PathNotAllowedError(ValueError):
    """Caminho fora da allowlist de leitura."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_read_roots() -> list[Path]:
    """Raízes padrão: docs/, data/knowledge/, vault opcional (YBY_VAULT_PATH)."""

    custom = os.getenv("YBY_TOOLS_READ_ROOTS", "").strip()
    if custom:
        roots = [Path(part.strip()).expanduser() for part in custom.split(",") if part.strip()]
        return [path.resolve() for path in roots]

    root = _repo_root()
    roots = [
        (root / "docs").resolve(),
        (root / "data" / "knowledge").resolve(),
    ]
    vault = os.getenv("YBY_VAULT_PATH", "").strip()
    if vault:
        roots.append(Path(vault).expanduser().resolve())
    return roots


def assert_allowed_path(path: Path | str, *, roots: list[Path] | None = None) -> Path:
    """Resolve o caminho e exige que fique dentro de alguma raiz allowlisted."""

    allowed = roots or default_read_roots()
    target = Path(path).expanduser()
    if not target.is_absolute():
        for root in allowed:
            candidate = (root / target).resolve()
            try:
                candidate.relative_to(root)
                return candidate
            except ValueError:
                continue
        raise PathNotAllowedError(f"caminho fora da allowlist: {path!r}")

    resolved = target.resolve()
    for root in allowed:
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue
    raise PathNotAllowedError(f"caminho fora da allowlist: {path!r}")