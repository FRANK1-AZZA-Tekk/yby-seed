"""Pipeline: dedupe → retry remoto → fila local."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.memory.episode_guard import EpisodeGuard, episode_fingerprint
from src.memory.pending_queue import PendingEpisodeQueue
from src.memory.remote_store import EpisodeRemoteClient, RemoteStoreError


@dataclass(frozen=True)
class EpisodeSaveResult:
    accepted: bool
    persisted: bool
    queued: bool


class EpisodePipeline:
    """Grava episódios com guarda, retry e fila offline."""

    def __init__(
        self,
        *,
        guard: EpisodeGuard | None = None,
        remote: EpisodeRemoteClient | None = None,
        queue: PendingEpisodeQueue | None = None,
        user_id: str = "yby",
    ) -> None:
        self.guard = guard or EpisodeGuard()
        self.remote = remote
        self.queue = queue
        self.user_id = user_id

    def save(
        self,
        source_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        *,
        now: float | None = None,
    ) -> EpisodeSaveResult:
        fp = episode_fingerprint(text, metadata)
        if not self.guard.should_accept(source_id, fp, now=now):
            return EpisodeSaveResult(accepted=False, persisted=False, queued=False)

        payload = {
            "messages": [{"role": "user", "content": text}],
            "user_id": self.user_id,
            "metadata": metadata or {},
            "source_id": source_id,
        }
        if self.remote is None:
            raise ValueError("cliente remoto não configurado")

        try:
            self.remote.add(
                payload["messages"],
                user_id=self.user_id,
                metadata=metadata,
            )
            return EpisodeSaveResult(accepted=True, persisted=True, queued=False)
        except RemoteStoreError:
            if self.queue is None:
                raise
            self.queue.enqueue(source_id, payload, now=now)
            return EpisodeSaveResult(accepted=True, persisted=False, queued=True)

    def flush_pending(self, *, limit: int = 32) -> int:
        """Reenvia episódios da fila; retorna quantos foram persistidos."""

        if self.remote is None or self.queue is None:
            return 0
        sent = 0
        for item in self.queue.list_batch(limit=limit):
            self.queue.mark_attempt(item.id)
            messages = item.payload.get("messages")
            if not isinstance(messages, list):
                self.queue.remove(item.id)
                continue
            meta = item.payload.get("metadata")
            user_id = str(item.payload.get("user_id", self.user_id))
            try:
                self.remote.add(
                    messages,
                    user_id=user_id,
                    metadata=meta if isinstance(meta, dict) else None,
                )
            except RemoteStoreError:
                break
            self.queue.remove(item.id)
            sent += 1
        return sent