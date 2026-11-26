"""Store em memória de YBYSpec com reuso por similaridade cosseno (>= 0.92)."""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from src.yby_machine.ports import AppSummary, StoredAppRecord
from src.yby_machine.spec import YBYSpec

DEFAULT_REUSE_THRESHOLD = 0.92


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Similaridade cosseno entre dois vetores. Retorna 0.0 se incompatíveis."""

    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemorySpecStore:
    """Store padrão em memória (offline, sem Postgres/Docker)."""

    def __init__(self, *, max_items: int = 256) -> None:
        if max_items < 1:
            raise ValueError("max_items deve ser >= 1")
        self._max_items = max_items
        self._records: list[tuple[StoredAppRecord, list[float]]] = []
        self._by_id: dict[str, StoredAppRecord] = {}

    async def find_similar(
        self,
        embedding: list[float],
        *,
        min_similarity: float = DEFAULT_REUSE_THRESHOLD,
    ) -> StoredAppRecord | None:
        best_record: StoredAppRecord | None = None
        best_score = -1.0
        for record, vec in self._records:
            score = cosine_similarity(embedding, vec)
            if score >= min_similarity and score > best_score:
                best_score = score
                best_record = record
        if best_record is None:
            return None
        return best_record.model_copy(update={"similarity": round(best_score, 6)})

    async def save(
        self,
        *,
        prompt: str,
        embedding: list[float],
        spec: YBYSpec,
        source: str,
    ) -> StoredAppRecord:
        app_id = uuid.uuid4().hex[:12]
        created_at = datetime.now(timezone.utc).isoformat()
        record = StoredAppRecord(
            app_id=app_id,
            prompt=prompt,
            spec=spec,
            source=source,
            created_at=created_at,
        )
        self._records.append((record, list(embedding)))
        self._by_id[app_id] = record
        while len(self._records) > self._max_items:
            old_record, _ = self._records.pop(0)
            self._by_id.pop(old_record.app_id, None)
        return record

    async def list_apps(self, *, limit: int = 50) -> list[AppSummary]:
        cap = max(1, int(limit))
        recent = reversed(self._records[-cap:])
        return [record.to_summary() for record, _ in recent]

    async def get_app(self, app_id: str) -> StoredAppRecord | None:
        return self._by_id.get(app_id)

    async def close(self) -> None:
        return None
