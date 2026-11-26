"""Serviço de pipeline de voz assíncrono não-bloqueante para o PC Hub."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.yby.audio.backends import AudioBackendError, STTBackend, TTSBackend
from src.yby.audio.device import AudioDeviceAdapter
from src.yby.audio.mqtt_bus import InMemoryMqttBus, MqttPublisher
from src.yby.audio.schemas import (
    TOPIC_AUDIO_STATE,
    TOPIC_TWATCH_CMD,
    AudioSessionState,
    AudioStateEvent,
    BluetoothProfile,
    TWatchCommand,
    VoiceTurnResult,
)
from src.yby.routing.router import CognitiveRouter
from src.yby.routing.schemas import RouteRequest

if TYPE_CHECKING:
    from src.yby.audio.twatch_bridge import TWatchBridge

logger = logging.getLogger("yby.audio.service")


@dataclass(frozen=True)
class AudioPipelineConfig:
    """Parâmetros do pipeline de áudio (CPU-first para preservar VRAM da GTX 1650)."""

    source_node: str = "desktop-yby"
    bt_device_name: str = "Baseus Bowie MC2 Air"
    state_topic: str = TOPIC_AUDIO_STATE
    twatch_cmd_topic: str = TOPIC_TWATCH_CMD
    sample_rate: int = 16_000
    max_record_seconds: float = 15.0
    language: str = "pt"
    kokoro_voice: str = "pf_dora"
    notify_twatch: bool = True

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> AudioPipelineConfig:
        source = environ if environ is not None else os.environ
        sample_raw = source.get("YBY_VOICE_SAMPLE_RATE", "16000").strip()
        max_raw = source.get("YBY_VOICE_MAX_SECONDS", "15").strip()
        try:
            sample_rate = int(sample_raw) if sample_raw else 16_000
        except ValueError as exc:
            raise ValueError(
                f"YBY_VOICE_SAMPLE_RATE inválido: {sample_raw!r}"
            ) from exc
        try:
            max_record_seconds = float(max_raw) if max_raw else 15.0
        except ValueError as exc:
            raise ValueError(
                f"YBY_VOICE_MAX_SECONDS inválido: {max_raw!r}"
            ) from exc
        return cls(
            source_node=source.get("YBY_NODE_ID", "desktop-yby").strip() or "desktop-yby",
            bt_device_name=(
                source.get("YBY_AUDIO_BT_DEVICE", "Baseus Bowie MC2 Air").strip()
                or "Baseus Bowie MC2 Air"
            ),
            state_topic=(
                source.get("YBY_AUDIO_STATE_TOPIC", TOPIC_AUDIO_STATE).strip()
                or TOPIC_AUDIO_STATE
            ),
            sample_rate=max(8_000, sample_rate),
            max_record_seconds=max(1.0, max_record_seconds),
            kokoro_voice=source.get("YBY_KOKORO_VOICE", "pf_dora").strip() or "pf_dora",
        )


class AsyncVoicePipeline:
    """Executa listening -> thinking -> speaking -> idle sem bloquear o event loop."""

    def __init__(
        self,
        *,
        device: AudioDeviceAdapter,
        stt: STTBackend,
        tts: TTSBackend,
        router: CognitiveRouter,
        mqtt_bus: MqttPublisher | None = None,
        config: AudioPipelineConfig | None = None,
        twatch_bridge: TWatchBridge | None = None,
    ) -> None:
        self.device = device
        self.stt = stt
        self.tts = tts
        self.router = router
        self.mqtt_bus = mqtt_bus or InMemoryMqttBus()
        self.config = config or AudioPipelineConfig()
        self.twatch_bridge = twatch_bridge
        self._state: AudioSessionState = "idle"
        self._lock = asyncio.Lock()
        self._background_tasks: set[asyncio.Task[VoiceTurnResult]] = set()

    @property
    def state(self) -> AudioSessionState:
        return self._state

    async def _set_state(
        self,
        state: AudioSessionState,
        *,
        profile: BluetoothProfile | None = None,
        detail: str = "",
    ) -> None:
        self._state = state
        event = AudioStateEvent(
            state=state,
            source_node=self.config.source_node,
            device=self.config.bt_device_name,
            profile=profile,
            detail=detail,
        )
        await self.mqtt_bus.publish(
            self.config.state_topic,
            event.model_dump_json(),
            qos=1,
            retain=True,
        )
        if self.twatch_bridge is not None and self.config.notify_twatch:
            await self.twatch_bridge.sync_audio_state(state, text=detail)

    async def _notify_twatch(self, text: str, state: AudioSessionState) -> None:
        if not self.config.notify_twatch:
            return
        cmd = TWatchCommand(
            command="display_text",
            text=text[:160],
            accent_color="#00FF66",
            state=state,
        )
        await self.mqtt_bus.publish(
            self.config.twatch_cmd_topic,
            cmd.model_dump_json(),
            qos=1,
            retain=False,
        )

    async def run_turn(
        self,
        *,
        wav_bytes: bytes | None = None,
        speak_reply: bool = True,
    ) -> VoiceTurnResult:
        """Executa um turno de voz ponta a ponta garantindo retorno ao estado `idle`."""

        async with self._lock:
            try:
                await self.device.set_profile("hfp")
                await self._set_state("listening", profile="hfp", detail="capturando áudio")

                captured = (
                    wav_bytes
                    if wav_bytes is not None
                    else await self.device.record_utterance(
                        max_seconds=self.config.max_record_seconds,
                        sample_rate=self.config.sample_rate,
                    )
                )

                await self._set_state("thinking", profile="hfp", detail="transcrevendo e roteando")
                transcript = await self.stt.transcribe(captured, language=self.config.language)

                # Áudio bruto de voz é SEMPRE privado (nunca sai para nuvem pelo PrivacyGate).
                route_reply = await self.router.route(
                    RouteRequest(
                        prompt=transcript,
                        sensitivity="private",
                        origin="raw_audio",
                        source_node=self.config.source_node,
                    )
                )

                await self._notify_twatch(route_reply.text, state="speaking")

                spoken = False
                audio_out_len = 0
                tts_error: str | None = None

                if speak_reply and route_reply.text.strip():
                    await self.device.set_profile("a2dp")
                    await self._set_state(
                        "speaking",
                        profile="a2dp",
                        detail="sintetizando resposta",
                    )
                    try:
                        wav_out = await self.tts.synthesize(
                            route_reply.text,
                            voice=self.config.kokoro_voice,
                        )
                        audio_out_len = len(wav_out)
                        await self.device.play_wav(wav_out)
                        spoken = True
                    except (AudioBackendError, RuntimeError) as exc:
                        tts_error = str(exc)

                return VoiceTurnResult(
                    transcript=transcript,
                    reply_text=route_reply.text,
                    route_tier=route_reply.tier,
                    route_model=route_reply.model,
                    audio_bytes_out=audio_out_len,
                    spoken=spoken,
                    error=tts_error,
                )
            finally:
                try:
                    await self._set_state("idle", detail="aguardando")
                except Exception as exc:  # noqa: BLE001
                    self._state = "idle"
                    logger.warning("Falha ao publicar estado idle no MQTT: %s", exc)

    def start_turn_background(
        self,
        *,
        wav_bytes: bytes | None = None,
        speak_reply: bool = True,
    ) -> asyncio.Task[VoiceTurnResult]:
        """Dispara um turno em background Task sem bloquear rotas HTTP do FastAPI."""

        task = asyncio.create_task(
            self.run_turn(wav_bytes=wav_bytes, speak_reply=speak_reply)
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task
