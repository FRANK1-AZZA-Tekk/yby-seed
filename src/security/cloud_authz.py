"""Authz de vault antes de egresso para nuvem (CLOUD_USAGE_SPEC §S4 / #42).

Sem `YBY_CLOUD_ALLOW_VAULT=1`, prompts que referenciam o path do vault
(`YBY_VAULT_PATH`) são bloqueados — não há strip silencioso.
Exception de budget não bypassa este gate.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

CODE_BLOCKED_AUTHZ = "blocked_authz"

_TRUE = frozenset({"1", "true", "yes", "on", "sim"})


@dataclass(frozen=True)
class AuthzDecision:
    """Resultado do gate de vault para um prompt de nuvem."""

    allowed: bool
    code: str
    reason: str


def vault_allowed(environ: dict[str, str] | None = None) -> bool:
    """YBY_CLOUD_ALLOW_VAULT default 0 — vault/refs só com grant explícito."""

    source = environ if environ is not None else os.environ
    raw = source.get("YBY_CLOUD_ALLOW_VAULT", "0").strip().casefold()
    if not raw:
        return False
    return raw in _TRUE


def vault_root(environ: dict[str, str] | None = None) -> Path | None:
    """Resolve YBY_VAULT_PATH; None se vazio."""

    source = environ if environ is not None else os.environ
    raw = source.get("YBY_VAULT_PATH", "").strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser().resolve()
    except OSError:
        return Path(raw).expanduser()


def check_cloud_prompt(
    text: str,
    *,
    environ: dict[str, str] | None = None,
) -> AuthzDecision:
    """Bloqueia se o texto cita o vault e não há ALLOW_VAULT."""

    if vault_allowed(environ):
        return AuthzDecision(True, "", "")

    root = vault_root(environ)
    if root is None:
        return AuthzDecision(True, "", "")

    if _prompt_references_vault(text, root):
        return AuthzDecision(
            False,
            CODE_BLOCKED_AUTHZ,
            (
                "Nuvem bloqueada: o prompt referencia o vault "
                f"({root}). Defina YBY_CLOUD_ALLOW_VAULT=1 para autorizar "
                "este envio (authz / #42)."
            ),
        )
    return AuthzDecision(True, "", "")


def _prompt_references_vault(text: str, root: Path) -> bool:
    if not text:
        return False
    markers = {
        str(root),
        root.as_posix(),
        f"file://{root.as_posix()}",
    }
    # Windows-style se aplicável
    try:
        markers.add(os.path.normcase(str(root)))
    except OSError:
        pass
    for marker in markers:
        if marker and marker in text:
            return True
    return False
