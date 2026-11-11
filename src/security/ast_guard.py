"""Guarda AST compartilhada para validação e sandbox.

Baseado em práticas públicas de sandboxes (allowlist de imports,
bloqueio de dunders/getattr/eval) e em advisories recentes
(PraisonAI, FastGPT, CVE-2026-55376): blocklist sozinha não basta.
"""

from __future__ import annotations

import ast

# Allowlist estrita — sem pathlib/io/os (podem abrir arquivos / escapar).
SAFE_IMPORTS: frozenset[str] = frozenset(
    {
        "math",
        "random",
        "datetime",
        "time",
        "collections",
        "itertools",
        "functools",
        "re",
        "json",
        "csv",
        "typing",
        "dataclasses",
        "string",
        "textwrap",
        "unicodedata",
        "decimal",
        "fractions",
        "statistics",
        "copy",
        "hashlib",
        "base64",
        "uuid",
    }
)

FORBIDDEN_NAMES: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "input",
        "breakpoint",
        "getattr",
        "setattr",
        "delattr",
        "globals",
        "locals",
        "vars",
        "dir",
        "help",
        "memoryview",
        "bytearray",
    }
)

DANGEROUS_ROOTS: frozenset[str] = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "multiprocessing",
        "socket",
        "http",
        "urllib",
        "requests",
        "ctypes",
        "pickle",
        "marshal",
        "shelve",
        "importlib",
        "pkgutil",
        "inspect",
        "pathlib",
        "io",
        "builtins",
        "shutil",
        "glob",
        "tempfile",
        "pty",
        "fcntl",
        "signal",
        "resource",
        "code",
        "codeop",
        "types",
    }
)


def _module_root(name: str | None) -> str | None:
    if not name:
        return None
    return name.split(".", 1)[0]


def validate_code_ast(code: str) -> tuple[bool, list[str]]:
    """Valida código com allowlist de imports e bloqueios de escape."""
    errors: list[str] = []

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, [f"Erro de sintaxe: {exc}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _module_root(alias.name)
                if root not in SAFE_IMPORTS:
                    errors.append(f"Import não permitido: {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                errors.append("Import relativo não permitido")
                continue
            root = _module_root(node.module)
            if root is None or root not in SAFE_IMPORTS:
                errors.append(f"ImportFrom não permitido: {node.module}")

        elif isinstance(node, ast.Attribute):
            attr = node.attr
            if attr.startswith("__") and attr.endswith("__"):
                errors.append(f"Acesso a dunder bloqueado: {attr}")

        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES or node.id in DANGEROUS_ROOTS:
                errors.append(f"Nome perigoso: {node.id}")

        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_NAMES:
                errors.append(f"Chamada proibida: {func.id}()")
            if isinstance(func, ast.Attribute) and func.attr in {
                "system",
                "popen",
                "exec",
                "execve",
                "spawn",
                "remove",
                "unlink",
                "rmtree",
            }:
                errors.append(f"Chamada perigosa: .{func.attr}()")

    # Dedup preservando ordem
    seen: set[str] = set()
    unique: list[str] = []
    for err in errors:
        if err not in seen:
            seen.add(err)
            unique.append(err)

    return len(unique) == 0, unique
