"""Schemas Pydantic do Módulo B (estado de áudio e contratos MQTT do T-Watch)."""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AudioSessionState = Literal["listening", "thinking", "speaking", "idle"]
BluetoothProfile = Literal["hfp", "a2dp"]

TOPIC_AUDIO_STATE = "yby/audio/state"
TOPIC_TWATCH_TELEMETRY = "yby/nodes/twatch/telemetry"
TOPIC_TWATCH_CMD = "yby/nodes/twatch/cmd"
TOPIC_TWATCH_VOICE = "yby/nodes/twatch/voice"


class AudioStateEvent(BaseModel):
    """Evento publicado em `yby/audio/state` (QoS 1, retain=True)."""

    model_config = ConfigDict(extra="forbid")

    state: AudioSessionState
    source_node: str = "desktop-yby"
    device: str = "Baseus Bowie MC2 Air"
    profile: BluetoothProfile | None = None
    detail: str = ""
    timestamp: float = Field(default_factory=time.time)


class TWatchTelemetry(BaseModel):
    """Contrato hub-side de telemetria enviada pelo T-Watch S3 Plus (sem firmware no repo)."""

    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(..., min_length=1, max_length=64)
    battery_pct: int = Field(..., ge=0, le=100)
    charging: bool = False
    wifi_rssi: int | None = None
    state: AudioSessionState = "idle"
    timestamp: float = Field(default_factory=time.time)


class TWatchCommand(BaseModel):
    """Contrato hub-side de comando curto para a UI minimalista do T-Watch."""

    model_config = ConfigDict(extra="forbid")

    command: Literal["display_text", "haptic_pulse", "set_state", "ping"]
    text: str = Field(default="", max_length=160)
    accent_color: Literal["#00FF66", "#F5F5F2", "#0D0D0D"] = "#00FF66"
    state: AudioSessionState | None = None
    timestamp: float = Field(default_factory=time.time)


class TWatchVoiceEnvelope(BaseModel):
    """Contrato hub-side para intenção/áudio oriundo do wearable (sempre privado)."""

    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(..., min_length=1, max_length=64)
    transcript: str | None = None
    audio_b64: str | None = None
    sample_rate: int = Field(default=16_000, ge=8_000, le=48_000)
    sensitivity: Literal["private"] = "private"
    timestamp: float = Field(default_factory=time.time)


class VoiceTurnResult(BaseModel):
    """Resultado de um turno completo do AsyncVoicePipeline."""

    model_config = ConfigDict(extra="forbid")

    transcript: str
    reply_text: str
    route_tier: str
    route_model: str
    audio_bytes_out: int = 0
    spoken: bool = False
    error: str | None = None
