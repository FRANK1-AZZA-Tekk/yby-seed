"""Limites de execução do subprocesso (lote 24 — sem sandbox OS)."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_TIMEOUT = 30.0
MAX_TIMEOUT = 120.0
MIN_TIMEOUT = 0.1
DEFAULT_OUTPUT_MAX_BYTES = 1_048_576  # 1 MiB
ARTIFACT_MANIFEST = Path(".yby") / "artifacts-manifest.json"


class RunnerLimitError(ValueError):
    """Timeout/limite de saída ou execução de artefato gerado inválidos."""


def timeout_from_env(environ: dict[str, str] | None = None) -> float:
    source = environ if environ is not None else os.environ
    raw = source.get("YBY_RUN_TIMEOUT", "").strip()
    if not raw:
        return DEFAULT_TIMEOUT
    return normalize_timeout(float(raw), environ=source)


def max_timeout_from_env(environ: dict[str, str] | None = None) -> float:
    source = environ if environ is not None else os.environ
    raw = source.get("YBY_RUN_TIMEOUT_MAX", "").strip()
    if not raw:
        return MAX_TIMEOUT
    value = float(raw)
    if value < MIN_TIMEOUT:
        raise RunnerLimitError(f"YBY_RUN_TIMEOUT_MAX deve ser >= {MIN_TIMEOUT}")
    return value


def output_max_bytes_from_env(environ: dict[str, str] | None = None) -> int:
    source = environ if environ is not None else os.environ
    raw = source.get("YBY_RUN_OUTPUT_MAX_BYTES", "").strip()
    if not raw:
        return DEFAULT_OUTPUT_MAX_BYTES
    value = int(raw)
    if value < 1024:
        raise RunnerLimitError("YBY_RUN_OUTPUT_MAX_BYTES deve ser >= 1024")
    return value


def normalize_timeout(
    timeout: float,
    *,
    environ: dict[str, str] | None = None,
) -> float:
    """Recusa timeout inválido e aplica teto YBY_RUN_TIMEOUT_MAX."""

    if timeout != timeout or timeout <= 0:  # NaN or non-positive
        raise RunnerLimitError(f"timeout inválido: {timeout!r}")
    capped = max_timeout_from_env(environ)
    if timeout < MIN_TIMEOUT:
        raise RunnerLimitError(f"timeout mínimo é {MIN_TIMEOUT:g}s")
    return min(float(timeout), capped)


def truncate_output(text: str, *, max_bytes: int) -> tuple[str, bool]:
    """Corta saída UTF-8 por bytes (não por codepoints)."""

    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return text, False
    kept = raw[:max_bytes].decode("utf-8", errors="ignore")
    marker = f"\n…[truncado: {len(raw)} bytes > limite {max_bytes}]\n"
    return kept + marker, True


def find_artifact_root(path: Path) -> Path | None:
    """Sobe diretórios até achar `.yby/artifacts-manifest.json` (scaffold aplicado)."""

    current = path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ARTIFACT_MANIFEST).is_file():
            return candidate
    return None


def assert_not_generated_execution(
    *,
    argv: list[str],
    workdir: Path,
) -> None:
    """Bloqueia subprocesso cujo cwd ou alvo esteja sob scaffold YBY aplicado."""

    hit = find_artifact_root(workdir)
    if hit is not None:
        raise RunnerLimitError(
            f"execução bloqueada: workdir sob artefato gerado ({hit / ARTIFACT_MANIFEST}). "
            "Sem sandbox OS no v1."
        )
    for arg in argv[1:]:
        if arg.startswith("-"):
            continue
        candidate = Path(arg)
        if not candidate.is_absolute():
            candidate = workdir / candidate
        if not candidate.exists():
            continue
        hit = find_artifact_root(candidate)
        if hit is not None:
            raise RunnerLimitError(
                f"execução bloqueada: argumento sob artefato gerado ({arg}). "
                "Sem sandbox OS no v1."
            )
