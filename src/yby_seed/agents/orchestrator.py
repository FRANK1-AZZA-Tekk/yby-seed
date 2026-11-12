"""Coordenação Architect → Builder → Sandbox → Auditor."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import paho.mqtt.client as mqtt
from openai import OpenAI

from src.yby_seed.agents.roles import ArchitectAgent, AuditorAgent, BuilderAgent
from src.yby_seed.agents.state import MissionState, MissionStatus
from src.yby_seed.config import Settings, get_settings
from src.yby_seed.models import GenerateRequest, GenerateResponse, StructuredCode
from src.yby_seed.persistence import append_dataset, publish_validated_code
from src.yby_seed.sandbox import execute_validated

mission_progress_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}


class MissionOrchestrator:
    def __init__(
        self,
        settings: Settings | None = None,
        client: OpenAI | None = None,
        progress_queue: asyncio.Queue[dict[str, Any]] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or OpenAI(
            base_url=self.settings.litellm_base_url,
            api_key=self.settings.litellm_api_key,
        )
        self._progress_queue = progress_queue
        self._architect = ArchitectAgent(self.client, self.settings)
        self._builder = BuilderAgent(self.client, self.settings)
        self._auditor = AuditorAgent(self.client, self.settings)

    async def run(self, request: GenerateRequest) -> GenerateResponse:
        mission_id = str(uuid.uuid4())
        queue = self._progress_queue or asyncio.Queue()
        mission_progress_queues[mission_id] = queue

        state = MissionState(
            mission_id=mission_id,
            user_intent=request.prompt,
            domain=request.domain,
            status=MissionStatus.PENDING,
        )

        try:
            return await self._run_mission(state, request, queue)
        finally:
            mission_progress_queues.pop(mission_id, None)

    async def _run_mission(
        self,
        state: MissionState,
        request: GenerateRequest,
        queue: asyncio.Queue[dict[str, Any]],
    ) -> GenerateResponse:
        state.status = MissionStatus.ARCHITECTING
        await self._emit(queue, state, "architect", "Consultando pgvector e planejando…")
        try:
            state = await self._architect.run(state)
        except Exception as exc:  # noqa: BLE001
            state.status = MissionStatus.FAILED
            await self._emit(queue, state, "architect", f"Falha: {exc}")
            return GenerateResponse(success=False, attempts=0, stderr=str(exc))

        artifact: StructuredCode | None = None
        last_stdout = ""
        last_stderr = ""

        for attempt in range(1, self.settings.max_generation_attempts + 1):
            state.attempt_count = attempt
            state.status = MissionStatus.BUILDING
            await self._emit(queue, state, "builder", f"Gerando código (tentativa {attempt})…")
            try:
                state = await self._builder.run(state)
                artifact = state.generated_code
            except Exception as exc:  # noqa: BLE001
                last_stderr = str(exc)
                state.validation_logs.append(last_stderr)
                continue

            if artifact is None:
                continue

            state.status = MissionStatus.VALIDATING
            await self._emit(queue, state, "sandbox", "Validando no Docker (sem rede)…")
            ok, last_stdout, last_stderr = execute_validated(
                language=artifact.language,
                code=artifact.code,
                filename=artifact.filename,
                tests=artifact.tests,
                settings=self.settings,
            )
            state.last_stdout = last_stdout
            state.last_stderr = last_stderr
            state.validation_logs.append(f"[sandbox] ok={ok} stderr={last_stderr[:500]}")

            if ok:
                state.status = MissionStatus.SUCCESS
                await self._emit(queue, state, "success", "Código validado.")
                system_prompt = request.system_prompt or "YBY SEED multiagent"
                dataset_saved = append_dataset(
                    self.settings.datasets_path,
                    system_prompt,
                    request.prompt,
                    artifact.code,
                )
                mqtt_published = publish_validated_code(self.settings, request, artifact)
                return GenerateResponse(
                    success=True,
                    attempts=attempt,
                    code=artifact.code,
                    filename=artifact.filename,
                    language=artifact.language,
                    stdout=last_stdout,
                    stderr=last_stderr,
                    dataset_saved=dataset_saved,
                    mqtt_published=mqtt_published,
                )

            state.status = MissionStatus.AUDITING
            await self._emit(queue, state, "auditor", "Diagnosticando stderr…")
            try:
                state = await self._auditor.run(state)
            except Exception as exc:  # noqa: BLE001
                state.auditor_guidance = str(exc)

        state.status = MissionStatus.FAILED
        await self._emit(queue, state, "failed", "Esgotadas tentativas de validação.")
        return GenerateResponse(
            success=False,
            attempts=state.attempt_count,
            code=artifact.code if artifact else None,
            filename=artifact.filename if artifact else None,
            language=artifact.language if artifact else None,
            stdout=last_stdout,
            stderr=last_stderr,
        )

    async def _emit(
        self,
        queue: asyncio.Queue[dict[str, Any]],
        state: MissionState,
        phase: str,
        message: str,
    ) -> None:
        event = {
            "mission_id": state.mission_id,
            "phase": phase,
            "status": state.status.value,
            "attempt": state.attempt_count,
            "message": message,
            "ts": datetime.now(UTC).isoformat(),
        }
        await queue.put(event)
        self._publish_trace(event)

    def _publish_trace(self, event: dict[str, Any]) -> None:
        topic = self.settings.mqtt_topic_agents_trace
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.connect(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=30)
            client.publish(topic, json.dumps(event, ensure_ascii=False), qos=0)
            client.disconnect()
        except Exception:  # noqa: BLE001
            return
