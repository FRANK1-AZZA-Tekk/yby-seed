#!/usr/bin/env python3
"""Checagem honesta do ambiente YBY SEED (local e CI).

Verifica apenas o que o núcleo precisa hoje: Python, arquivos-chave,
imports das deps listadas e ferramentas de lint/teste. Não inventa
serviços (Ollama, Qdrant, nuvem) — esses são opcionais e avisados.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MIN_PY = (3, 11)

REQUIRED_FILES = (
    "yby.py",
    "src/main.py",
    "requirements.txt",
    "requirements-dev.txt",
    "Makefile",
    "pyproject.toml",
    "tests",
    ".github/workflows/ci.yml",
)

# Pacotes mínimos do núcleo (requirements.txt) usados no caminho ask/CLI.
CORE_IMPORTS = (
    "click",
    "pydantic",
    "dotenv",
    "loguru",
    "requests",
)

# Ferramentas que o Makefile/CI chamam.
DEV_IMPORTS = (
    "ruff",
    "pytest",
)


def _ok(msg: str) -> None:
    print(f"OK  {msg}")


def _fail(msg: str) -> None:
    print(f"FAIL {msg}", file=sys.stderr)


def _warn(msg: str) -> None:
    print(f"WARN {msg}")


def check_python() -> bool:
    if sys.version_info < MIN_PY:
        _fail(f"Python {MIN_PY[0]}.{MIN_PY[1]}+ necessário; achou {sys.version.split()[0]}")
        return False
    _ok(f"Python {sys.version.split()[0]}")
    return True


def check_files() -> bool:
    ok = True
    for rel in REQUIRED_FILES:
        path = ROOT / rel
        if not path.exists():
            _fail(f"arquivo/pasta ausente: {rel}")
            ok = False
        else:
            _ok(f"presente: {rel}")
    return ok


def check_imports(names: tuple[str, ...], label: str) -> bool:
    ok = True
    for name in names:
        try:
            importlib.import_module(name)
            _ok(f"import {label}: {name}")
        except ImportError as exc:
            _fail(f"import {label}: {name} ({exc})")
            ok = False
    return ok


def check_make_targets() -> bool:
    makefile = ROOT / "Makefile"
    text = makefile.read_text(encoding="utf-8")
    ok = True
    for target in ("doctor", "lint", "test"):
        # Alvo no início da linha: "doctor:" ou ".PHONY: ... doctor"
        if f"\n{target}:" not in f"\n{text}" and not text.startswith(f"{target}:"):
            _fail(f"Makefile sem alvo `{target}`")
            ok = False
        else:
            _ok(f"Makefile tem `{target}`")
    return ok


def check_optional_hints() -> None:
    # Avisos apenas — não falham o doctor.
    try:
        importlib.import_module("litellm")
        _ok("opcional: litellm importável")
    except ImportError:
        _warn("litellm não importável (está em requirements.txt; rode make setup)")

    _warn("Ollama/Qdrant/nuvem não são exigidos pelo doctor; use-os só se a tarefa precisar")


def main() -> int:
    print(f"YBY SEED doctor — raiz: {ROOT}")
    results = [
        check_python(),
        check_files(),
        check_imports(CORE_IMPORTS, "core"),
        check_imports(DEV_IMPORTS, "dev"),
        check_make_targets(),
    ]
    check_optional_hints()
    if all(results):
        print("doctor: PASS")
        return 0
    print("doctor: FAIL", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
