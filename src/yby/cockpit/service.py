"""Serviço local-first do Cockpit PhoneBox (status, inbox Obsidian, RAG e MQTT)."""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.yby.audio.mqtt_bus import MqttPublisher, PahoMqttPublisher
from src.yby.cockpit.schemas import (
    CockpitServicesStatus,
    CockpitStatusResponse,
    CockpitWebhookRequest,
    CockpitWebhookResponse,
    ServiceHealth,
)
from src.yby.edge_sync.worker import EdgeSyncWorker
from src.yby.obsidian_rag import ObsidianVaultIndexer, create_obsidian_store_from_env
from src.yby_machine.ports import SpecStorePort

ServiceProbe = Callable[[], Awaitable[ServiceHealth]]
_MAX_MQTT_PAYLOAD_BYTES = 8192


class CockpitActionError(RuntimeError):
    """Erro operacional tipado ao executar uma ação do webhook do Cockpit."""

    def __init__(self, detail: str, *, status_code: int = 503) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_host_port(raw_url: str, default_port: int) -> tuple[str, int] | None:
    text = (raw_url or "").strip()
    if not text:
        return None
    candidate = text if "://" in text else f"tcp://{text}"
    parsed = urlparse(candidate)
    host = parsed.hostname
    if not host:
        return None
    return host, int(parsed.port or default_port)


async def _tcp_probe(host: str, port: int, *, timeout: float = 0.2) -> ServiceHealth:
    start = time.perf_counter()
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
        return ServiceHealth(status="up", latency_ms=elapsed_ms, detail=f"{host}:{port}")
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
        return ServiceHealth(
            status="down",
            latency_ms=elapsed_ms,
            detail=f"{host}:{port} ({type(exc).__name__})",
        )


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


class CockpitService:
    """Orquestra telemetria leve e ações táteis do PhoneBox (Moto Edge 30)."""

    def __init__(
        self,
        *,
        vault_path: Path | str | None = None,
        indexer: ObsidianVaultIndexer | None = None,
        mqtt_bus: MqttPublisher | None = None,
        spec_store: SpecStorePort | None = None,
        edge_worker: EdgeSyncWorker | None = None,
        service_probes: Mapping[str, ServiceProbe] | None = None,
        probe_timeout: float = 0.2,
        clock: Callable[[], datetime] | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self._env: Mapping[str, str] = environ if environ is not None else os.environ
        self._vault_path = Path(vault_path) if vault_path is not None else None
        self.indexer = indexer or ObsidianVaultIndexer(
            store=create_obsidian_store_from_env(self._env)
        )
        self.mqtt_bus = mqtt_bus
        self.spec_store = spec_store
        self.edge_worker = edge_worker
        self._service_probes = dict(service_probes or {})
        self.probe_timeout = max(0.05, float(probe_timeout))
        self._clock = clock or _utc_now
        self._active_tasks = 0

    def _resolve_vault_root(self) -> Path:
        if self._vault_path is not None:
            return self._vault_path
        raw = self._env.get("YBY_VAULT_PATH", "").strip()
        if not raw:
            raise CockpitActionError(
                "YBY_VAULT_PATH não configurado para operações no cofre Obsidian",
                status_code=503,
            )
        return Path(raw)

    async def _probe_redis(self) -> ServiceHealth:
        if "redis" in self._service_probes:
            return await self._service_probes["redis"]()
        target = _parse_host_port(self._env.get("YBY_REDIS_URL", ""), 6379)
        if target is None:
            return ServiceHealth(status="unconfigured", detail="YBY_REDIS_URL não definido")
        return await _tcp_probe(target[0], target[1], timeout=self.probe_timeout)

    async def _probe_postgres(self) -> ServiceHealth:
        if "postgres_pgvector" in self._service_probes:
            return await self._service_probes["postgres_pgvector"]()
        dsn = (
            self._env.get("YBY_PGVECTOR_DSN")
            or self._env.get("YBY_DATABASE_URL")
            or ""
        ).strip()
        target = _parse_host_port(dsn, 5432)
        if target is None:
            return ServiceHealth(
                status="unconfigured",
                detail="YBY_PGVECTOR_DSN/YBY_DATABASE_URL não definido",
            )
        return await _tcp_probe(target[0], target[1], timeout=self.probe_timeout)

    async def _probe_mqtt(self) -> ServiceHealth:
        if "mqtt" in self._service_probes:
            return await self._service_probes["mqtt"]()
        if self.mqtt_bus is not None and not isinstance(self.mqtt_bus, PahoMqttPublisher):
            return ServiceHealth(status="up", latency_ms=0.0, detail="in-memory-bus")
        host = self._env.get("YBY_MQTT_HOST", "").strip()
        if not host and isinstance(self.mqtt_bus, PahoMqttPublisher):
            host = self.mqtt_bus.host
        if not host:
            return ServiceHealth(status="unconfigured", detail="YBY_MQTT_HOST não definido")
        raw_port = self._env.get("YBY_MQTT_PORT", "1883").strip()
        port = int(raw_port) if raw_port.isdigit() else 1883
        return await _tcp_probe(host, port, timeout=self.probe_timeout)

    async def _count_machine_specs(self) -> int:
        if self.spec_store is None:
            return 0
        try:
            apps = await self.spec_store.list_apps(limit=200)
            return len(apps)
        except Exception:  # noqa: BLE001
            return 0

    async def _count_pending_edge_events(self) -> int:
        if self.edge_worker is None:
            return 0
        try:
            edge_status = await self.edge_worker.status()
            return int(edge_status.pending_fallback)
        except Exception:  # noqa: BLE001
            return 0

    async def _count_indexed_chunks(self) -> int:
        try:
            return int(await self.indexer.store.count_chunks())
        except Exception:  # noqa: BLE001
            return 0

    async def get_status(self) -> CockpitStatusResponse:
        """Retorna snapshot compacto de serviços locais, specs e fila de tarefas."""

        redis_h, pg_h, mqtt_h, specs_count, pending_edge, indexed_chunks = await asyncio.gather(
            self._probe_redis(),
            self._probe_postgres(),
            self._probe_mqtt(),
            self._count_machine_specs(),
            self._count_pending_edge_events(),
            self._count_indexed_chunks(),
        )
        services = CockpitServicesStatus(
            fastapi=ServiceHealth(status="up", latency_ms=0.0, detail="local-hub"),
            redis=redis_h,
            postgres_pgvector=pg_h,
            mqtt=mqtt_h,
        )
        any_down = any(
            svc.status == "down"
            for svc in (services.redis, services.postgres_pgvector, services.mqtt)
        )
        return CockpitStatusResponse(
            status="degraded" if any_down else "ok",
            timestamp=self._clock().isoformat(),
            services=services,
            yby_machine_specs_count=specs_count,
            active_tasks=self._active_tasks,
            pending_edge_events=pending_edge,
            indexed_chunks=indexed_chunks,
        )

    def _capture_inbox(self, req: CockpitWebhookRequest) -> dict[str, Any]:
        vault_root = self._resolve_vault_root().resolve()
        vault_root.mkdir(parents=True, exist_ok=True)
        now = self._clock()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M UTC")

        rel_path = f"00-inbox/{date_str}.md"
        target = (vault_root / rel_path).resolve()
        try:
            target.relative_to(vault_root)
        except ValueError as exc:
            raise CockpitActionError("caminho da nota fora do cofre", status_code=400) from exc

        created = not target.exists()
        if created:
            header = (
                "---\n"
                "type: inbox\n"
                f"date: {date_str}\n"
                f"source: {req.source}\n"
                "offline_ready: true\n"
                "tags:\n"
                "  - inbox\n"
                "  - phonebox\n"
                "---\n\n"
                f"# Inbox — {date_str}\n"
            )
            existing = header
        else:
            existing = target.read_text(encoding="utf-8")

        heading_suffix = f" — {req.title}" if req.title else ""
        tag_line = (
            "\n" + " ".join(f"#{tag}" for tag in req.tags)
            if req.tags
            else ""
        )
        entry = (
            f"\n## {time_str}{heading_suffix}\n\n"
            f"- **Origem:** `{req.source}`\n\n"
            f"{req.note}{tag_line}\n"
        )
        updated = existing.rstrip() + "\n" + entry
        _atomic_write_text(target, updated)

        return {
            "relative_path": rel_path,
            "created": created,
            "bytes_written": len(updated.encode("utf-8")),
        }

    async def _trigger_reindex(self, req: CockpitWebhookRequest) -> dict[str, Any]:
        vault_root = self._resolve_vault_root()
        self._active_tasks += 1
        try:
            report = await self.indexer.reindex_vault(vault_root, force=req.force_reindex)
            return report.model_dump(mode="json")
        finally:
            self._active_tasks = max(0, self._active_tasks - 1)

    def _resolve_mqtt_bus(self) -> MqttPublisher:
        if self.mqtt_bus is not None:
            return self.mqtt_bus
        host = self._env.get("YBY_MQTT_HOST", "").strip()
        if not host:
            raise CockpitActionError(
                "Broker MQTT não configurado (defina YBY_MQTT_HOST ou injete mqtt_bus)",
                status_code=503,
            )
        raw_port = self._env.get("YBY_MQTT_PORT", "1883").strip()
        port = int(raw_port) if raw_port.isdigit() else 1883
        self.mqtt_bus = PahoMqttPublisher(
            host=host,
            port=port,
            client_id="yby-cockpit-bridge",
        )
        return self.mqtt_bus

    async def _publish_mqtt(self, req: CockpitWebhookRequest) -> dict[str, Any]:
        bus = self._resolve_mqtt_bus()
        envelope = {
            "source": req.source,
            "timestamp": self._clock().isoformat(),
            "topic": req.mqtt_topic,
            "payload": req.mqtt_payload or {},
        }
        encoded = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
        payload_bytes = len(encoded.encode("utf-8"))
        if payload_bytes > _MAX_MQTT_PAYLOAD_BYTES:
            raise CockpitActionError(
                f"payload MQTT excede limite seguro de {_MAX_MQTT_PAYLOAD_BYTES} bytes",
                status_code=400,
            )
        try:
            await bus.publish(req.mqtt_topic, encoded, qos=1, retain=False)
        except Exception as exc:  # noqa: BLE001
            raise CockpitActionError(
                f"falha ao publicar no broker MQTT: {exc}",
                status_code=503,
            ) from exc
        return {
            "topic": req.mqtt_topic,
            "bytes": payload_bytes,
            "qos": 1,
        }

    async def handle_webhook(self, req: CockpitWebhookRequest) -> CockpitWebhookResponse:
        """Despacha comandos táteis validados do PhoneBox."""

        if req.action == "capture_inbox":
            data = await asyncio.to_thread(self._capture_inbox, req)
            return CockpitWebhookResponse(
                ok=True,
                action=req.action,
                detail=f"nota gravada em {data['relative_path']}",
                data=data,
            )

        if req.action == "trigger_reindex":
            data = await self._trigger_reindex(req)
            return CockpitWebhookResponse(
                ok=True,
                action=req.action,
                detail=(
                    f"reindexação concluída ({data['files_indexed']} indexados, "
                    f"{data['files_skipped']} inalterados)"
                ),
                data=data,
            )

        if req.action == "publish_mqtt":
            data = await self._publish_mqtt(req)
            return CockpitWebhookResponse(
                ok=True,
                action=req.action,
                detail=f"payload publicado em {data['topic']}",
                data=data,
            )

        raise CockpitActionError(f"ação não suportada: {req.action}", status_code=400)
