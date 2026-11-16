"""Allowlist de caminhos, extensões seguras e caminhos relativos."""

from __future__ import annotations

import os
from pathlib import Path

SAFE_READ_EXTENSIONS = frozenset({".md", ".txt", ".json", ".yaml", ".yml", ".pdf"})
_SENSITIVE_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        "credentials.json",
        "secrets.json",
        "id_rsa",
        "id_ed25519",
    }
)


class PathNotAllowedError(ValueError):
    """Caminho fora da allowlist de leitura."""


class UnsafePathError(ValueError):
    """Traversal, symlink ou extensão não permitida."""


class UnsafeContentError(ValueError):
    """Conteúdo binário ou arquivo sensível."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_read_roots() -> list[Path]:
    """Raízes padrão: docs/, data/knowledge/, vault opcional (YBY_VAULT_PATH)."""

    custom = os.getenv("YBY_TOOLS_READ_ROOTS", "").strip()
    if custom:
        roots = [Path(part.strip()).expanduser() for part in custom.split(",") if part.strip()]
        return [_ensure_resolved_no_symlink(path) for path in roots]

    root = _repo_root()
    roots = [
        (root / "docs").resolve(),
        (root / "data" / "knowledge").resolve(),
    ]
    vault = os.getenv("YBY_VAULT_PATH", "").strip()
    if vault:
        roots.append(Path(vault).expanduser().resolve())
    return [_ensure_resolved_no_symlink(path) for path in roots]


def _ensure_resolved_no_symlink(path: Path) -> Path:
    resolved = path.resolve()
    if path.is_symlink():
        raise UnsafePathError(f"symlink não permitido na raiz: {path}")
    return resolved


def _reject_symlink_chain(path: Path) -> None:
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise UnsafePathError("symlink não permitido")
        if part == part.anchor:
            break


def _reject_traversal_tokens(raw: str) -> None:
    normalized = raw.replace("\\", "/")
    if ".." in normalized.split("/"):
        raise UnsafePathError("path traversal (..) não permitido")


def assert_allowed_path(path: Path | str, *, roots: list[Path] | None = None) -> Path:
    """Resolve o caminho e exige que fique dentro de alguma raiz allowlisted (sem symlinks)."""

    allowed = roots or default_read_roots()
    raw = str(path).strip()
    _reject_traversal_tokens(raw)
    target = Path(raw).expanduser()

    if target.is_symlink():
        raise UnsafePathError("symlink não permitido")

    if not target.is_absolute():
        for root in allowed:
            combined = root / target
            _reject_symlink_chain(combined)
            candidate = combined.resolve()
            try:
                candidate.relative_to(root.resolve())
                return candidate
            except ValueError:
                continue
        raise PathNotAllowedError(f"caminho fora da allowlist: {raw!r}")

    resolved = target.resolve()
    if resolved.is_symlink():
        raise UnsafePathError("symlink não permitido")
    for root in allowed:
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue
    raise PathNotAllowedError(f"caminho absoluto fora da allowlist: {raw!r}")


def assert_safe_file_name(name: str) -> None:
    if name in _SENSITIVE_NAMES or name.startswith(".env"):
        raise UnsafeContentError(f"arquivo sensível bloqueado: {name}")


def assert_safe_extension(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix not in SAFE_READ_EXTENSIONS:
        raise UnsafePathError(
            f"extensão não permitida: {suffix or '(sem extensão)'} "
            f"(permitidas: {', '.join(sorted(SAFE_READ_EXTENSIONS))})"
        )


def relative_to_root(path: Path, *, roots: list[Path]) -> str:
    resolved = path.resolve()
    for root in roots:
        try:
            return resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    return path.name


def root_for_path(path: Path, *, roots: list[Path]) -> Path | None:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return root
        except ValueError:
            continue
    return None


def looks_binary(raw: bytes) -> bool:
    if b"\x00" in raw[:4096]:
        return True
    if not raw:
        return False
    try:
        raw[:8192].decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False