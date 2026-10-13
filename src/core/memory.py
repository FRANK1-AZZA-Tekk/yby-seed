"""Memória persistente local do YBY SEED."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class MemoryEntry:
    question: str
    answer: str
    created_at: str


class MemoryStore:
    """Memória simples e persistente em JSONL.

    Cada linha é um objeto JSON. O arquivo é local e não deve ser versionado.
    """

    def __init__(self, path: Path | None = None):
        self.path = path or Path(".yby/memory.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, question: str, answer: str) -> MemoryEntry:
        entry = MemoryEntry(
            question=question,
            answer=answer,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        return entry

    def list(self) -> list[MemoryEntry]:
        if not self.path.exists():
            return []
        entries: list[MemoryEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            entries.append(MemoryEntry(**data))
        return entries

    def search(self, question: str, limit: int = 3) -> list[MemoryEntry]:
        query = {word.lower() for word in question.split() if len(word) > 2}
        scored: list[tuple[int, MemoryEntry]] = []
        for entry in self.list():
            text = f"{entry.question} {entry.answer}".lower()
            overlap = len(query & {word for word in text.split() if len(word) > 2})
            if overlap:
                scored.append((overlap, entry))
        scored.sort(key=lambda item: -item[0])
        return [entry for _, entry in scored[:limit]]
