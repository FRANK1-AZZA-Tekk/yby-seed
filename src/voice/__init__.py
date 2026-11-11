"""Voz local-first: STT (faster-whisper) e TTS (Piper). Opcionais no v1."""

from src.voice.config import VoiceConfig, voice_config_from_env
from src.voice.session import VoiceError, listen_once

__all__ = [
    "VoiceConfig",
    "VoiceError",
    "listen_once",
    "voice_config_from_env",
]
