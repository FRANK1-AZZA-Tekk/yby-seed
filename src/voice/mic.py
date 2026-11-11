"""Gravação push-to-talk: grava até Enter. sounddevice é opcional."""

from __future__ import annotations

import tempfile
import threading
import wave
from collections.abc import Callable
from pathlib import Path

from src.voice.config import VoiceConfig


class MicError(RuntimeError):
    """Microfone ou dependência de áudio ausente."""


def check_mic() -> tuple[bool, str]:
    try:
        import sounddevice  # noqa: F401
    except ImportError:
        return (
            False,
            "sounddevice não instalado. Rode: pip install -r requirements-voice.txt",
        )
    return True, "sounddevice disponível"


def record_until_enter(
    config: VoiceConfig,
    *,
    input_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], None] | None = None,
) -> Path:
    """Grava do microfone até a pessoa apertar Enter. Retorna WAV 16-bit mono."""

    ok, message = check_mic()
    if not ok:
        raise MicError(message)

    import sounddevice as sd

    say = output_fn or (lambda _msg: None)
    wait = input_fn or input

    frames: list = []
    stop = threading.Event()

    def _callback(indata, _frames, _time, status) -> None:  # noqa: ANN001
        if status:
            say(f"aviso do microfone: {status}")
        if not stop.is_set():
            frames.append(indata.copy())

    say("Gravando… aperte Enter para parar.")
    try:
        with sd.InputStream(
            samplerate=config.sample_rate,
            channels=1,
            dtype="int16",
            callback=_callback,
        ):
            wait("")
    except Exception as exc:  # noqa: BLE001
        raise MicError(f"Não deu para abrir o microfone: {exc}") from exc
    finally:
        stop.set()

    if not frames:
        raise MicError("Nenhum áudio capturado.")

    import numpy as np

    audio = np.concatenate(frames, axis=0)
    path = Path(tempfile.mkstemp(prefix="yby-mic-", suffix=".wav")[1])
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(config.sample_rate)
        wav.writeframes(audio.tobytes())
    return path
