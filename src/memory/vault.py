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
        index = self._sync_index()
        query_vector = _vector(query)
        scored = [
            Hit(name, _dot(query_vector, vector))
            for name, vector in index.items()
            if vector
        ]
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

    def _load_records(self) -> dict[str, tuple[list[float], float]]:
        if not self.index_path.is_file():
            return {}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        notes = data.get("notes", {})
        if not isinstance(notes, dict):
            return {}
        records: dict[str, tuple[list[float], float]] = {}
        for name, raw in notes.items():
            if not isinstance(name, str):
                continue
            if isinstance(raw, list):
                records[name] = ([float(value) for value in raw], 0.0)
            elif isinstance(raw, dict) and isinstance(raw.get("v"), list):
                mtime = raw.get("m", 0.0)
                stamp = float(mtime) if isinstance(mtime, (int, float)) else 0.0
                records[name] = ([float(value) for value in raw["v"]], stamp)
        return records

    def _write_records(self, records: dict[str, tuple[list[float], float]]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "notes": {
                name: {"v": vector, "m": mtime} for name, (vector, mtime) in records.items()
            }
        }
        # Escrita atômica: crash no meio do write_text corrompia o índice.
        temporary = self.index_path.with_suffix(self.index_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(temporary, self.index_path)

    def _update_index(self, name: str, body: str) -> None:
        records = self._load_records()
        path = self.root / name
        mtime = path.stat().st_mtime if path.is_file() else 0.0
        records[name] = (_vector(body), mtime)
        self._write_records(records)

    def _sync_index(self) -> dict[str, list[float]]:
        """Reindexa notas criadas ou editadas fora de `write_note` (Obsidian)."""

        records = self._load_records()
        changed = False
        seen: set[str] = set()
        for path in self.root.rglob("*.md"):
            if ".yby" in path.parts:
                continue
            rel = self._relative(path)
            seen.add(rel)
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            current = records.get(rel)
            if current is not None and current[1] >= mtime:
                continue
            try:
                body = path.read_text(encoding="utf-8")
            except OSError:
                continue
            records[rel] = (_vector(body), mtime)
            changed = True
        for name in [name for name in records if name not in seen]:
            del records[name]
            changed = True
        if changed:
            self._write_records(records)
        return {name: vector for name, (vector, _mtime) in records.items()}


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
