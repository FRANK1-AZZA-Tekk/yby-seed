"""Mapa compacto de símbolos (Python AST + heurísticas C/C++)."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from src.yby_seed.sandbox.hardware_linter import BOARD_CONSTRAINTS, BOARD_IDS

_PY_SUFFIX = {".py"}
_CPP_SUFFIX = {".c", ".cc", ".cpp", ".h", ".hpp"}

_CPP_STRUCT = re.compile(r"^\s*(?:typedef\s+)?struct\s+(\w+)", re.M)
_CPP_DEFINE = re.compile(r"^\s*#define\s+(\w+)", re.M)
_CPP_FN = re.compile(
    r"^\s*(?:static\s+)?(?:inline\s+)?[\w\s\*&:]+\s+(\w+)\s*\([^;]*\)\s*\{",
    re.M,
)


def _signature_py(node: ast.AST) -> str:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        args = [a.arg for a in node.args.args]
        return f"def {node.name}({', '.join(args)})"
    if isinstance(node, ast.ClassDef):
        bases = [ast.unparse(b) for b in node.bases] if node.bases else []
        base_part = f"({', '.join(bases)})" if bases else ""
        return f"class {node.name}{base_part}"
    return ""


def _map_python_file(path: Path) -> dict[str, Any]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as exc:
        return {"file": str(path), "error": str(exc), "symbols": []}

    symbols: list[dict[str, str]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            sig = _signature_py(node)
            if sig:
                symbols.append(
                    {"kind": node.__class__.__name__, "name": node.name, "signature": sig}
                )
    return {"file": path.name, "language": "python", "symbols": symbols}


def _map_cpp_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    symbols: list[dict[str, str]] = []
    for match in _CPP_STRUCT.finditer(text):
        symbols.append(
            {"kind": "struct", "name": match.group(1), "signature": f"struct {match.group(1)}"}
        )
    for match in _CPP_DEFINE.finditer(text):
        symbols.append(
            {"kind": "define", "name": match.group(1), "signature": f"#define {match.group(1)}"}
        )
    for match in _CPP_FN.finditer(text):
        symbols.append(
            {
                "kind": "function",
                "name": match.group(1),
                "signature": match.group(0).split("{", 1)[0].strip(),
            }
        )
    return {"file": path.name, "language": "cpp", "symbols": symbols}


def _gpio_manifest(domain: str | None) -> dict[str, Any]:
    boards = {
        bid: {k: sorted(v) for k, v in pins.items()} for bid, pins in BOARD_CONSTRAINTS.items()
    }
    if domain and domain in BOARD_IDS:
        return {"domain": domain, "boards": {domain: boards.get(domain, {})}}
    return {"boards": boards, "board_ids": list(BOARD_IDS)}


def build_repo_map(
    path: str | Path, domain: str | None = None, *, max_files: int = 120
) -> dict[str, Any]:
    """Constrói mapa de símbolos para um diretório de projeto."""
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"diretório inválido: {root}")

    files_out: list[dict[str, Any]] = []
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()
        if suffix in _PY_SUFFIX:
            files_out.append(_map_python_file(file_path))
        elif suffix in _CPP_SUFFIX:
            files_out.append(_map_cpp_file(file_path))
        if len(files_out) >= max_files:
            break

    return {
        "root": str(root),
        "domain": domain,
        "file_count": len(files_out),
        "files": files_out,
        "gpio_manifest": _gpio_manifest(domain),
    }
