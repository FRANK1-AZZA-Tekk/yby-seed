"""Ponte hub-side do Módulo C (T-Watch S3 Plus: atalhos 2C, telemetria e alertas 5A)."""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import ValidationError

from src.yby.audio.mqtt_bus import InMemoryMqttBus, MqttPublisher
from src.yby.audio.schemas import (
    TOPIC_TWATCH_CMD,
    AudioSessionState,
    TWatchCommand,
    TWatchTelemetry,
    TWatchVoiceEnvelope,
)
from src.yby.routing.router import CognitiveRouter
from src.yby.routing.schemas import RouteRequest, RouteResponse

logger = logging.getLogger("yby.audio.twatch_bridge")

HapticPattern = Literal["short_pulse", "micro_tick", "solid_arc", "double_pulse", "none"]
AccentHex = Literal["#00FF66", "#F5F5F2", "#0D0D0D"]


def map_audio_state_feedback(state: AudioSessionState) -> tuple[HapticPattern, AccentHex]:
    """Mapeia `yby/audio/state` para padrão háptico (DRV2605) e cor LVGL (5A)."""

    mapping: dict[AudioSessionState, tuple[HapticPattern, AccentHex]] = {
        "listening": ("short_pulse", "#00FF66"),
        "thinking": ("micro_tick", "#F5F5F2"),
        "speaking": ("solid_arc", "#F5F5F2"),
        "idle": ("none", "#0D0D0D"),
    }
    return mapping[state]


class TWatchBridge:
    """Conecta eventos do T-Watch S3 Plus ao CognitiveRouter, yby_machine e MQTT."""

    def __init__(
        self,
        *,
        router: CognitiveRouter,
        mqtt_bus: MqttPublisher | None = None,
        cmd_topic: str = TOPIC_TWATCH_CMD,
    ) -> None:
        self.router = router
        self.mqtt_bus = mqtt_bus or InMemoryMqttBus()
        self.cmd_topic = cmd_topic
        self.latest_telemetry: dict[str, TWatchTelemetry] = {}

    def handle_telemetry_message(self, raw_payload: str | bytes) -> TWatchTelemetry | None:
        """Valida e registra última telemetria de `yby/nodes/twatch/telemetry`."""

        text = raw_payload.decode("utf-8", errors="replace") if isinstance(raw_payload, bytes) else raw_payload
        try:
            telemetry = TWatchTelemetry.model_validate_json(text)
        except ValidationError as exc:
            logger.warning("Telemetria T-Watch inválida ignorada: %s", exc)
            return None
        self.latest_telemetry[telemetry.device_id] = telemetry
        return telemetry

    async def handle_voice_message(self, raw_payload: str | bytes) -> RouteResponse | None:
        """Roteia atalho 2C (`yby/nodes/twatch/voice`) de forma fail-closed e devolve resposta."""

        text = raw_payload.decode("utf-8", errors="replace") if isinstance(raw_payload, bytes) else raw_payload
        try:
            envelope = TWatchVoiceEnvelope.model_validate_json(text)
        except ValidationError as exc:
            logger.warning("Envelope de voz T-Watch inválido ignorado: %s", exc)
            return None

        prompt = (envelope.transcript or "").strip()
        if not prompt:
            logger.info("Envelope T-Watch %s sem transcript utilizável", envelope.device_id)
            return None

        reply = await self.router.route(
            RouteRequest(
                prompt=prompt,
                sensitivity="private",
                origin="user_prompt",
                source_node=envelope.device_id,
            )
        )

        cmd = TWatchCommand(
            command="display_text",
            text=reply.text.strip()[:160],
            accent_color="#00FF66",
            state="idle",
        )
        await self.mqtt_bus.publish(
            self.cmd_topic,
            cmd.model_dump_json(),
            qos=1,
            retain=False,
        )
        return reply

    async def emit_machine_alert(
        self,
        app_name: str,
        message: str,
        *,
        accent_color: AccentHex = "#00FF66",
    ) -> TWatchCommand:
        """Publica notificação do `yby_machine` com pulso duplo no relógio (5A)."""

        clean_app = app_name.strip() or "YBY"
        clean_msg = message.strip() or "Atualização concluída"
        formatted = f"[{clean_app}] {clean_msg}"[:160]
        cmd = TWatchCommand(
            command="haptic_pulse",
            text=formatted,
            accent_color=accent_color,
            state="idle",
        )
        await self.mqtt_bus.publish(
            self.cmd_topic,
            cmd.model_dump_json(),
            qos=1,
            retain=False,
        )
        return cmd
