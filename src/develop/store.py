"""Persistência de planos (contrato painel) e exports MD."""

from __future__ import annotations

import json
import time
from pathlib import Path

from src.develop.schemas import DevelopPlan, LayerStatus


def default_develop_root() -> Path:
    return Path.home() / ".local" / "state" / "yby-seed" / "develop"


def plans_dir(root: Path | None = None) -> Path:
    return (root or default_develop_root()) / "plans"


def exports_dir(root: Path | None = None) -> Path:
    return (root or default_develop_root()) / "exports"


def plan_path(plan_id: str, *, root: Path | None = None) -> Path:
    safe = plan_id.replace("/", "_").replace("..", "_")
    return plans_dir(root) / f"{safe}.json"


def save_plan(plan: DevelopPlan, *, root: Path | None = None) -> Path:
    path = plan_path(plan.id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    plan.updated_at = time.time()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(plan.to_painel_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def load_plan(plan_id: str, *, root: Path | None = None) -> DevelopPlan:
    path = plan_path(plan_id, root=root)
    if not path.is_file():
        raise FileNotFoundError(f"plano não encontrado: {plan_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return DevelopPlan.model_validate(data)


def set_layer_status(
    plan: DevelopPlan,
    layer_id: str,
    status: LayerStatus,
    *,
    root: Path | None = None,
) -> DevelopPlan:
    layer = plan.layer(layer_id)
    if layer is None:
        raise KeyError(f"camada inexistente: {layer_id}")
    layer.status = status
    save_plan(plan, root=root)
    return plan
