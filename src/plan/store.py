"""Persistência de planos versionados (JSON local)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from src.plan.schemas import YbyPlan


class PlanStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, plan_id: str, version: int | None = None) -> Path:
        safe = plan_id.strip().replace("/", "").replace("..", "")
        if not safe:
            raise ValueError("id inválido")
        if version is None:
            return self.root / f"{safe}.json"
        return self.root / f"{safe}.v{version}.json"

    def save(self, plan: YbyPlan) -> Path:
        latest = self.path_for(plan.id)
        versioned = self.path_for(plan.id, plan.version)
        payload = json.dumps(plan.model_dump(), ensure_ascii=False, indent=2) + "\n"
        latest.write_text(payload, encoding="utf-8")
        versioned.write_text(payload, encoding="utf-8")
        return latest

    def load(self, plan_id: str, version: int | None = None) -> YbyPlan:
        path = self.path_for(plan_id) if version is None else self.path_for(plan_id, version)
        if not path.is_file():
            raise FileNotFoundError(f"plano inexistente: {plan_id}")
        return YbyPlan.model_validate_json(path.read_text(encoding="utf-8"))


def load_or_create_plan_store(explicit: Path | None = None) -> PlanStore:
    if explicit is not None:
        return PlanStore(explicit)
    vault = os.environ.get("YBY_VAULT_PATH", "").strip()
    if vault:
        return PlanStore(Path(vault).expanduser() / ".yby" / "plans")
    return PlanStore(Path.cwd() / ".yby" / "plans")
