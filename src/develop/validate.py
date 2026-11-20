"""Validação de plano: paths no checkout, deps e ciclos."""

from __future__ import annotations

from pathlib import Path

from src.develop.schemas import DevelopPlan, Layer

_BLOCKED_PREFIXES = (".env", "vault/", ".git/")
_BLOCKED_NAMES = {".env", ".env.local", ".env.production"}


class PlanValidationError(ValueError):
    """Plano inválido."""


def validate_plan(plan: DevelopPlan, *, repo_root: Path) -> None:
    root = repo_root.resolve()
    if not plan.layers:
        raise PlanValidationError("plano sem camadas")

    ids = [layer.id for layer in plan.layers]
    if len(ids) != len(set(ids)):
        raise PlanValidationError("ids de camada duplicados")

    id_set = set(ids)
    for layer in plan.layers:
        for dep in layer.depends_on:
            if dep not in id_set:
                raise PlanValidationError(
                    f"camada {layer.id}: dependência inexistente {dep!r}"
                )
            if dep == layer.id:
                raise PlanValidationError(f"camada {layer.id}: auto-dependência")
        _validate_paths(layer, root=root)

    _reject_cycles(plan.layers)


def _validate_paths(layer: Layer, *, root: Path) -> None:
    for raw in layer.allowed_files:
        path = _normalize_rel(raw)
        if path is None:
            raise PlanValidationError(
                f"camada {layer.id}: caminho inválido {raw!r}"
            )
        lowered = path.as_posix().lower()
        name = path.name
        if name in _BLOCKED_NAMES or any(lowered.startswith(p) for p in _BLOCKED_PREFIXES):
            raise PlanValidationError(
                f"camada {layer.id}: caminho bloqueado {raw!r}"
            )
        # deve ficar sob o checkout (relativo, sem escapar)
        resolved = (root / path).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise PlanValidationError(
                f"camada {layer.id}: fora do checkout {raw!r}"
            ) from exc


def _normalize_rel(raw: str) -> Path | None:
    text = raw.strip().replace("\\", "/")
    if not text or text.startswith("/") or ".." in Path(text).parts:
        return None
    return Path(text)


def _reject_cycles(layers: list[Layer]) -> None:
    graph = {layer.id: list(layer.depends_on) for layer in layers}
    visiting: set[str] = set()
    done: set[str] = set()

    def dfs(node: str) -> None:
        if node in done:
            return
        if node in visiting:
            raise PlanValidationError(f"ciclo de dependências envolvendo {node}")
        visiting.add(node)
        for dep in graph.get(node, []):
            dfs(dep)
        visiting.remove(node)
        done.add(node)

    for layer_id in graph:
        dfs(layer_id)
