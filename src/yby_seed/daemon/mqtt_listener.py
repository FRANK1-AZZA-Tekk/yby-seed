"""Worker MQTT autônomo com semáforo VRAM (GTX 1650 4GB)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import paho.mqtt.client as mqtt

from src.yby_seed.config import Settings, get_settings
from src.yby_seed.engine import SeedEngine
from src.yby_seed.mcp.tools import check_gpu_headroom
from src.yby_seed.models import DomainKind, GenerateRequest

logger = logging.getLogger(__name__)


class MqttAutonomyWorker:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._engine = SeedEngine(self.settings)
        self._queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()
        self._sem = asyncio.Semaphore(self._max_concurrency())
        self._task: asyncio.Task[None] | None = None
        self._client: mqtt.Client | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _max_concurrency(self) -> int:
        return int(getattr(self.settings, "mqtt_max_concurrent_jobs", 1) or 1)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.connect_async(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=60)
        self._client.loop_start()
        self._task = asyncio.create_task(self._consume())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
        self._client = None

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: object,
        reason_code: mqtt.ReasonCode,
        properties: object | None = None,
    ) -> None:
        client.subscribe("yby/seed/request/#", qos=1)
        logger.info("MQTT autônomo inscrito em yby/seed/request/#")

    def _on_message(self, client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
        if self._loop is None:
            return
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        request_id = str(payload.get("id") or msg.topic.split("/")[-1])
        self._loop.call_soon_threadsafe(self._queue.put_nowait, (request_id, payload))

    async def _consume(self) -> None:
        while True:
            request_id, payload = await self._queue.get()
            asyncio.create_task(self._handle_request(request_id, payload))

    async def _handle_request(self, request_id: str, payload: dict[str, Any]) -> None:
        async with self._sem:
            gpu = await asyncio.to_thread(check_gpu_headroom)
            if gpu.get("decision") != "process_local":
                self._publish(
                    request_id,
                    {
                        "id": request_id,
                        "status": "queued",
                        "reason": gpu.get("reason"),
                    },
                )
                return

            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                self._publish(request_id, {"id": request_id, "status": "error", "error": "prompt vazio"})
                return

            domain_raw = payload.get("domain", "python_fastapi")
            domain: DomainKind = domain_raw if domain_raw in {
                "python_fastapi",
                "esp_idf",
                "lvgl_v9",
                "modbus_rtu",
            } else "python_fastapi"

            try:
                response = await self._engine.generate(GenerateRequest(prompt=prompt, domain=domain))
                self._publish(
                    request_id,
                    {
                        "id": request_id,
                        "status": "ok" if response.success else "failed",
                        "success": response.success,
                        "attempts": response.attempts,
                        "code": response.code,
                        "validation_report": response.validation_report,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._publish(request_id, {"id": request_id, "status": "error", "error": str(exc)})

    def _publish(self, request_id: str, body: dict[str, Any]) -> None:
        if self._client is None:
            return
        topic = f"yby/seed/response/{request_id}"
        self._client.publish(topic, json.dumps(body, ensure_ascii=False), qos=1)
