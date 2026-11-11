"""Configuração da camada de voz. Modelos cabem no PC Hub (GTX 1650 / CPU)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv

# `base` cabe bem em CPU e em 4 GB VRAM; `small` é opcional via env.
DEFAULT_WHISPER_MODEL = "base"
DEFAULT_WHISPER_DEVICE = "cpu"
DEFAULT_WHISPER_COMPUTE = "int8"
DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_PIPER_BIN = "piper"
DEFAULT_PLAY_BIN = "aplay"


@dataclass(frozen=True)
class VoiceConfig:
    """Caminhos e modelos de STT/TTS. Sem segredos."""

    whisper_model: str
    whisper_device: str
    whisper_compute_type: str
    sample_rate: int
    piper_bin: str
    piper_model: str
    play_bin: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> VoiceConfig:
        if environ is None:
            load_dotenv(override=False)
            source: Mapping[str, str] = os.environ
        else:
            source = environ

        sample_raw = source.get("YBY_VOICE_SAMPLE_RATE", "").strip()
        sample_rate = int(sample_raw) if sample_raw else DEFAULT_SAMPLE_RATE
        if sample_rate < 8_000:
            raise ValueError("YBY_VOICE_SAMPLE_RATE deve ser >= 8000.")

        return cls(
            whisper_model=_text(source, "YBY_WHISPER_MODEL") or DEFAULT_WHISPER_MODEL,
            whisper_device=_text(source, "YBY_WHISPER_DEVICE") or DEFAULT_WHISPER_DEVICE,
            whisper_compute_type=_text(source, "YBY_WHISPER_COMPUTE") or DEFAULT_WHISPER_COMPUTE,
            sample_rate=sample_rate,
            piper_bin=_text(source, "YBY_PIPER_BIN") or DEFAULT_PIPER_BIN,
            piper_model=_text(source, "YBY_PIPER_MODEL"),
            play_bin=_text(source, "YBY_PLAY_BIN") or DEFAULT_PLAY_BIN,
        )


def voice_config_from_env() -> VoiceConfig:
    return VoiceConfig.from_env()


def _text(source: Mapping[str, str], name: str) -> str:
    return source.get(name, "").strip()
