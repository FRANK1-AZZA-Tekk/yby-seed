"""Persistência local do YBY-BRIEF (JSON). Vault path opcional."""

from __future__ import annotations

import json
import os
from pathlib import Path

from src.brief.schemas import YbyBrief


class BriefStore:
    """Pasta `.yby/briefs/` sob vault (se YBY_VAULT_PATH) ou cwd."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, brief_id: str) -> Path:
        safe = brief_id.strip().replace("/", "").replace("..", "")
        if not safe:
            raise ValueError("id inválido")
        return self.root / f"{safe}.json"

    def save(self, brief: YbyBrief) -> Path:
        path = self.path_for(brief.id)
        path.write_text(
            json.dumps(brief.model_dump(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def load(self, brief_id: str) -> YbyBrief:
        path = self.path_for(brief_id)
        if not path.is_file():
            raise FileNotFoundError(f"brief inexistente: {brief_id}")
        return YbyBrief.model_validate_json(path.read_text(encoding="utf-8"))

    def list_ids(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.json"))


def load_or_create_store(explicit: Path | None = None) -> BriefStore:
    """Resolve diretório: `--dir` > `YBY_VAULT_PATH/.yby/briefs` > `./.yby/briefs`."""

    if explicit is not None:
        return BriefStore(explicit)
    vault = os.environ.get("YBY_VAULT_PATH", "").strip()
    if vault:
        return BriefStore(Path(vault).expanduser() / ".yby" / "briefs")
    return BriefStore(Path.cwd() / ".yby" / "briefs")
