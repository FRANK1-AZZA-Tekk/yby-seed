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

FORBIDDEN_DUNDER_IDS: frozenset[str] = frozenset(
    {
        "__builtins__",
        "__class__",
        "__subclasses__",
        "__globals__",
        "__locals__",
        "__code__",
        "__closure__",
        "__dict__",
        "__bases__",
        "__mro__",
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

DANGEROUS_ATTRS: frozenset[str] = frozenset(
    {
        "system",
        "popen",
        "exec",
        "execve",
        "spawn",
        "remove",
        "unlink",
        "rmtree",
        "load",
        "loads",
        "dump",
        "dumps",
        "connect",
        "send",
        "recv",
        "urlopen",
        "request",
        "makedirs",
        "mkdir",
    }
)

_SUBSCRIPT_KEYS = FORBIDDEN_NAMES | DANGEROUS_ATTRS | FORBIDDEN_DUNDER_IDS


def _module_root(name: str | None) -> str | None:
    if not name:
        return None
    return name.split(".", 1)[0]


def _string_key(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _root_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _root_name(node.value)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return _root_name(node.func.value)
    return None


def _is_dunder(attr: str) -> bool:
    return attr.startswith("__") and attr.endswith("__") and len(attr) >= 4


def _json_serialization_attr(root: str | None, attr: str) -> bool:
    """json.dump(s) na allowlist; pickle.dumps e similares continuam bloqueados."""
    return root == "json" and attr in {"dump", "dumps"}


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

        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES or node.id in DANGEROUS_ROOTS:
                errors.append(f"Nome perigoso: {node.id}")
            elif node.id in FORBIDDEN_DUNDER_IDS:
                errors.append(f"Dunder proibido: {node.id}")

        elif isinstance(node, ast.Attribute):
            attr = node.attr
            if _is_dunder(attr) or attr in FORBIDDEN_DUNDER_IDS:
                errors.append(f"Acesso a dunder bloqueado: {attr}")
            root = _root_name(node.value)
            if attr in DANGEROUS_ATTRS and not _json_serialization_attr(root, attr):
                errors.append(f"Atributo perigoso: {attr}")
            if attr in FORBIDDEN_NAMES:
                errors.append(f"Nome perigoso em atributo: {attr}")
            if root in DANGEROUS_ROOTS or root in FORBIDDEN_DUNDER_IDS or root == "builtins":
                errors.append(f"Acesso via raiz perigosa: {root}.{attr}")

        elif isinstance(node, ast.Subscript):
            key = _string_key(node.slice)
            if key and key in _SUBSCRIPT_KEYS:
                errors.append(f"Subscript proibido: [{key!r}]")
            base_root = _root_name(node.value)
            if base_root in FORBIDDEN_DUNDER_IDS | DANGEROUS_ROOTS | frozenset({"builtins"}):
                errors.append(f"Subscript em raiz perigosa: {base_root}")
            if key and base_root in {"globals", "locals", "vars", "getattr"}:
                errors.append(f"Acesso dinâmico proibido: {base_root}[{key!r}]")

        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_NAMES:
                errors.append(f"Chamada proibida: {func.id}()")
            if isinstance(func, ast.Attribute) and func.attr in DANGEROUS_ATTRS:
                call_root = _root_name(func.value)
                if not _json_serialization_attr(call_root, func.attr):
                    errors.append(f"Chamada perigosa: .{func.attr}()")
            if isinstance(func, ast.Subscript):
                key = _string_key(func.slice)
                if key and key in _SUBSCRIPT_KEYS:
                    errors.append(f"Chamada via subscript proibida: [{key!r}]()")

    seen: set[str] = set()
    unique: list[str] = []
    for err in errors:
        if err not in seen:
            seen.add(err)
            unique.append(err)

    return len(unique) == 0, unique
