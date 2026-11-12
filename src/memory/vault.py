"""Vault Obsidian: notas Markdown e um índice vetorial local."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

_TOKEN = re.compile(r"[0-9A-Za-zÀ-ÿ]+")
_DIM = 64


@dataclass(frozen=True)
class Hit:
    """Nota encontrada na busca."""

    name: str
    score: float


class VaultError(ValueError):
    """Caminho de nota inválido."""


class Vault:
    """Lê e grava Markdown. O Syncthing sincroniza a pasta; este módulo não."""

    def __init__(self, path: Path):
        self.root = path
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / ".yby" / "index.json"

    def write_note(self, name: str, body: str) -> Path:
        path = self._note_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        self._update_index(self._relative(path), body)
        return path

    def read_note(self, name: str) -> str:
        path = self._note_path(name)
        if not path.is_file():
            raise VaultError(f"nota inexistente: {name}")
        return path.read_text(encoding="utf-8")

    def list_notes(self) -> list[str]:
        notes: list[str] = []
        for path in self.root.rglob("*.md"):
            if ".yby" in path.parts:
                continue
            notes.append(self._relative(path))
        return sorted(notes)

    def search(self, query: str, k: int = 3) -> list[Hit]:
        index = self._load_index()
        query_vector = _vector(query)
        scored = [Hit(name, _dot(query_vector, vector)) for name, vector in index.items() if vector]
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return [hit for hit in scored[:k] if hit.score > 0]

    def _note_path(self, name: str) -> Path:
        cleaned = name.strip().replace("\\", "/")
        if not cleaned or cleaned.startswith("/"):
            raise VaultError("nome de nota inválido")
        if not cleaned.endswith(".md"):
            cleaned = f"{cleaned}.md"
        path = (self.root / cleaned).resolve()
        try:
            path.relative_to(self.root.resolve())
        except ValueError as exc:
            raise VaultError("a nota precisa ficar dentro do vault") from exc
        return path

    def _relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    def _load_index(self) -> dict[str, list[float]]:
        if not self.index_path.is_file():
            return {}
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        notes = data.get("notes", {})
        return {name: list(vector) for name, vector in notes.items()}

    def _update_index(self, name: str, body: str) -> None:
        notes = self._load_index()
        notes[name] = _vector(body)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"notes": notes}
        self.index_path.write_text(json.dumps(payload), encoding="utf-8")


def vault_from_env() -> Vault:
    """Abre o vault apontado por YBY_VAULT_PATH."""

    raw = os.getenv("YBY_VAULT_PATH", "").strip()
    if not raw:
        raise VaultError("defina YBY_VAULT_PATH")
    return Vault(Path(raw))


def _vector(text: str) -> list[float]:
    buckets = [0.0] * _DIM
    for token in _TOKEN.findall(text.casefold()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        buckets[int.from_bytes(digest[:2], "big") % _DIM] += 1.0
    norm = math.sqrt(sum(value * value for value in buckets)) or 1.0
    return [value / norm for value in buckets]


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))
