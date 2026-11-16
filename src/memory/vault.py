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


@dataclass(frozen=True)
class ReindexStats:
    """Resultado de reindexação incremental por content-hash."""

    added: int
    updated: int
    unchanged: int
    removed: int

    @property
    def total(self) -> int:
        return self.added + self.updated + self.unchanged


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
        scored = [
            Hit(name, _dot(query_vector, vector))
            for name, vector in index.items()
            if vector and (self.root / name).is_file()
        ]
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return [hit for hit in scored[:k] if hit.score > 0]

    def reindex(self) -> ReindexStats:
        """Reconcilia disco → índice via content-hash (não usa mtime).

        Arquivos novos/alterados são re-vetorizados; inalterados são
        reaproveitados; entradas órfãs (apagadas no disco) saem do índice.
        """

        notes, hashes = self._load_index_state()
        new_notes: dict[str, list[float]] = {}
        new_hashes: dict[str, str] = {}
        added = updated = unchanged = 0

        for name in self.list_notes():
            body = (self.root / name).read_text(encoding="utf-8")
            digest = _content_hash(body)
            previous = hashes.get(name)
            if previous == digest and name in notes:
                new_notes[name] = notes[name]
                new_hashes[name] = digest
                unchanged += 1
                continue
            new_notes[name] = _vector(body)
            new_hashes[name] = digest
            if previous is None and name not in notes:
                added += 1
            else:
                updated += 1

        removed = len(set(notes) - set(new_notes))
        self._write_index_state(new_notes, new_hashes)
        return ReindexStats(
            added=added, updated=updated, unchanged=unchanged, removed=removed
        )

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
        notes, _hashes = self._load_index_state()
        return notes

    def _load_index_state(self) -> tuple[dict[str, list[float]], dict[str, str]]:
        if not self.index_path.is_file():
            return {}, {}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VaultError(
                "índice corrompido (.yby/index.json); rode yby reindex"
            ) from exc
        if not isinstance(data, dict):
            raise VaultError(
                "índice corrompido (.yby/index.json); rode yby reindex"
            )
        raw_notes = data.get("notes", {})
        if not isinstance(raw_notes, dict):
            raise VaultError(
                "índice corrompido (.yby/index.json); rode yby reindex"
            )
        notes = {name: list(vector) for name, vector in raw_notes.items()}
        raw_hashes = data.get("hashes", {})
        if not isinstance(raw_hashes, dict):
            raw_hashes = {}
        hashes = {name: str(value) for name, value in raw_hashes.items()}
        return notes, hashes

    def _write_index_state(
        self, notes: dict[str, list[float]], hashes: dict[str, str]
    ) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"notes": notes, "hashes": hashes}
        self.index_path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def _update_index(self, name: str, body: str) -> None:
        notes, hashes = self._load_index_state()
        notes[name] = _vector(body)
        hashes[name] = _content_hash(body)
        self._write_index_state(notes, hashes)


def vault_from_env() -> Vault:
    """Abre o vault apontado por YBY_VAULT_PATH."""

    raw = os.getenv("YBY_VAULT_PATH", "").strip()
    if not raw:
        raise VaultError("defina YBY_VAULT_PATH")
    return Vault(Path(raw))


def _content_hash(text: str) -> str:
    """Fingerprint do corpo (não mtime) — estável sob Syncthing/git checkout."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _vector(text: str) -> list[float]:
    buckets = [0.0] * _DIM
    for token in _TOKEN.findall(text.casefold()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        buckets[int.from_bytes(digest[:2], "big") % _DIM] += 1.0
    norm = math.sqrt(sum(value * value for value in buckets)) or 1.0
    return [value / norm for value in buckets]


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))
