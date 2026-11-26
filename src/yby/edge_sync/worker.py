"""Worker assíncrono de ingestão idempotente e dreno do Xiaomi 12 para o PC Hub."""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

import httpx

from src.yby.audio.mqtt_bus import MqttPublisher
from src.yby.audio.schemas import TOPIC_AUDIO_STATE
from src.yby.edge_sync.schemas import (
    EdgeEvent,
    EdgeSyncBatchRequest,
    EdgeSyncBatchResponse,
    EdgeSyncStatus,
)
from src.yby.edge_sync.store import SQLiteFallbackEdgeStore, VectorEventStore

HUB_REPUBLISH_MARKER = "hub_republished"


@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float] | None: ...


class OllamaEmbeddingProvider:
    """Gera embeddings locais via Ollama (`all-minilm:22m`, 384 dims) sem nuvem."""

    def __init__(
        self,
        *,
        ollama_host: str = "http://127.0.0.1:11434",
        model: str = "all-minilm:22m",
        timeout: float = 15.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.ollama_host = ollama_host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._external_client = http_client

    async def embed(self, text: str) -> list[float] | None:
        clean = text.strip()
        if not clean:
            return None
        url = f"{self.ollama_host}/api/embeddings"
        payload = {"model": self.model, "prompt": clean}
        try:
            if self._external_client is not None:
                resp = await self._external_client.post(url, json=payload)
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            vec = data.get("embedding")
            if isinstance(vec, list) and vec:
                return [float(x) for x in vec]
        except Exception:  # noqa: BLE001
            return None
        return None


def _build_embedding_text(event: EdgeEvent) -> str:
    if event.text_summary.strip():
        return event.text_summary.strip()
    return f"{event.topic} {json.dumps(event.payload, ensure_ascii=False, sort_keys=True)}"


class EdgeSyncWorker:
    """Recebe lotes do Xiaomi 12 (Termux), persiste com idempotência e evita eco MQTT."""

    def __init__(
        self,
        *,
        primary_store: VectorEventStore,
        fallback_store: SQLiteFallbackEdgeStore | None = None,
        embedder: EmbeddingProvider | None = None,
        mqtt_bus: MqttPublisher | None = None,
    ) -> None:
        self.primary_store = primary_store
        self.fallback_store = fallback_store
        self.embedder = embedder
        self.mqtt_bus = mqtt_bus

    async def _maybe_republish(self, event: EdgeEvent) -> None:
        if self.mqtt_bus is None:
            return
        # Previne loop infinito de sincronização e não sobrescreve tópico de estado de áudio.
        if event.sync_origin == HUB_REPUBLISH_MARKER:
            return
        if event.topic == TOPIC_AUDIO_STATE:
            return
        envelope = {
            "event_id": event.event_id,
            "device_id": event.device_id,
            "source_node": event.source_node,
            "captured_at": event.captured_at,
            "payload": event.payload,
            "sync_origin": HUB_REPUBLISH_MARKER,
        }
        await self.mqtt_bus.publish(
            event.topic,
            json.dumps(envelope, ensure_ascii=False),
            qos=1,
            retain=False,
        )

    async def ingest_batch(self, batch: EdgeSyncBatchRequest) -> EdgeSyncBatchResponse:
        accepted = 0
        duplicates = 0
        failed = 0
        last_cursor: str | None = None
        used_backend = self.primary_store.backend_name

        for event in batch.events:
            embedding = event.embedding
            if embedding is None and self.embedder is not None:
                embedding = await self.embedder.embed(_build_embedding_text(event))

            try:
                status = await self.primary_store.upsert_event(event, embedding)
            except Exception:  # noqa: BLE001
                if self.fallback_store is None:
                    failed += 1
                    continue
                try:
                    status = await self.fallback_store.upsert_event(event, embedding)
                    used_backend = self.fallback_store.backend_name
                except Exception:  # noqa: BLE001
                    failed += 1
                    continue

            last_cursor = event.event_id
            if status == "inserted":
                accepted += 1
                await self._maybe_republish(event)
            else:
                duplicates += 1

        return EdgeSyncBatchResponse(
            accepted=accepted,
            duplicates=duplicates,
            failed=failed,
            last_cursor=last_cursor,
            store_backend=used_backend,
        )

    async def drain_fallback(self, *, batch_size: int = 64) -> dict[str, int]:
        if self.fallback_store is None:
            return {"inserted": 0, "duplicates": 0, "remaining": 0}
        inserted, duplicates = await self.fallback_store.drain_to(
            self.primary_store,
            batch_size=batch_size,
        )
        remaining = await self.fallback_store.count_pending()
        return {"inserted": inserted, "duplicates": duplicates, "remaining": remaining}

    async def status(self) -> EdgeSyncStatus:
        pending = (
            await self.fallback_store.count_pending()
            if self.fallback_store is not None
            else 0
        )
        try:
            total = await self.primary_store.count_events()
            return EdgeSyncStatus(
                store_backend=self.primary_store.backend_name,
                total_stored=total,
                pending_fallback=pending,
                healthy=True,
            )
        except Exception:  # noqa: BLE001
            return EdgeSyncStatus(
                store_backend=self.primary_store.backend_name,
                total_stored=0,
                pending_fallback=pending,
                healthy=False,
            )
