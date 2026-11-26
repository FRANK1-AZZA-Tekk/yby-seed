"""Módulo B — Pipeline de voz não-bloqueante (Baseus Bowie MC2 Air + MQTT)."""

from __future__ import annotations

from src.yby.audio.backends import (
    AudioBackendError,
    KokoroTTSBackend,
    STTBackend,
    TTSBackend,
    WhisperCppBackend,
)
from src.yby.audio.device import (
    AudioDeviceAdapter,
    CommandRunner,
    PipeWireBluetoothDevice,
    SubprocessCommandRunner,
    has_voice_activity,
)
from src.yby.audio.mqtt_bus import (
    InMemoryMqttBus,
    MqttPublisher,
    PahoMqttBridgeSubscriber,
    PahoMqttPublisher,
    PublishedMessage,
)
from src.yby.audio.schemas import (
    TOPIC_AUDIO_STATE,
    TOPIC_TWATCH_CMD,
    TOPIC_TWATCH_TELEMETRY,
    TOPIC_TWATCH_VOICE,
    AudioSessionState,
    AudioStateEvent,
    BluetoothProfile,
    TWatchCommand,
    TWatchTelemetry,
    TWatchVoiceEnvelope,
    VoiceTurnResult,
)
from src.yby.audio.service import AsyncVoicePipeline, AudioPipelineConfig
from src.yby.audio.twatch_bridge import TWatchBridge, map_audio_state_feedback

__all__ = [
    "TOPIC_AUDIO_STATE",
    "TOPIC_TWATCH_CMD",
    "TOPIC_TWATCH_TELEMETRY",
    "TOPIC_TWATCH_VOICE",
    "AsyncVoicePipeline",
    "AudioBackendError",
    "AudioDeviceAdapter",
    "AudioPipelineConfig",
    "AudioSessionState",
    "AudioStateEvent",
    "BluetoothProfile",
    "CommandRunner",
    "InMemoryMqttBus",
    "KokoroTTSBackend",
    "MqttPublisher",
    "PahoMqttBridgeSubscriber",
    "PahoMqttPublisher",
    "PipeWireBluetoothDevice",
    "PublishedMessage",
    "STTBackend",
    "SubprocessCommandRunner",
    "TTSBackend",
    "TWatchBridge",
    "TWatchCommand",
    "TWatchTelemetry",
    "TWatchVoiceEnvelope",
    "VoiceTurnResult",
    "WhisperCppBackend",
    "has_voice_activity",
    "map_audio_state_feedback",
]
