"""Captura PTT no terminal Linux. YBY_VOICE_INPUT_DEVICE seleciona a entrada."""

from __future__ import annotations

import os
import select
import sys
import tempfile
import threading
import time
import wave
from collections.abc import Callable
from pathlib import Path

from src.voice.config import VoiceConfig


class MicError(RuntimeError):
    """Dependência, dispositivo ou captura indisponível."""


def check_mic() -> tuple[bool, str]:
    try:
        import sounddevice  # noqa: F401
    except (ImportError, OSError):
        return False, "Áudio indisponível. Confira requirements-voice.txt e PortAudio."
    return True, "sounddevice disponível; entrada será validada ao gravar"


def _input_device() -> int | str | None:
    raw = os.environ.get("YBY_VOICE_INPUT_DEVICE", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return raw


def _terminal_stop(timeout: float) -> bool:
    try:
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
    except (OSError, ValueError, TypeError) as exc:
        raise MicError("Use um terminal Linux com entrada interativa disponível.") from exc
    if not ready:
        return False
    if sys.stdin.readline() == "":
        raise MicError("Entrada encerrada (EOF); gravação cancelada.")
    return True


def record_until_enter(
    config: VoiceConfig,
    *,
    input_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], None] | None = None,
) -> Path:
    """Retorna WAV mono int16. Enter ou limite encerram a captura.

    input_fn é hook síncrono legado e precisa retornar prontamente.
    A CLI padrão usa polling POSIX, sem thread bloqueada em input().
    """
    ok, message = check_mic()
    if not ok:
        raise MicError(message)
    if config.sample_rate <= 0 or config.max_seconds <= 0:
        raise MicError("Taxa de amostragem e duração devem ser positivas.")
    import sounddevice as sd

    say = output_fn or (lambda _msg: None)
    device = _input_device()
    try:
        info = sd.query_devices(device, "input")
        if info["max_input_channels"] < 1:
            raise MicError("Dispositivo não tem canal de entrada.")
        sd.check_input_settings(
            device=device, channels=1, dtype="int16", samplerate=config.sample_rate
        )
    except MicError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MicError(f"Entrada de áudio inválida ({device!r}): {exc}") from exc

    frames: list = []
    notices: list = []
    errors: list = []
    done = threading.Event()
    captured = 0
    budget = int(config.sample_rate * config.max_seconds)

    def _callback(indata, _frames, _time, status) -> None:  # noqa: ANN001
        nonlocal captured
        if done.is_set():
            return
        try:
            if status and not notices:
                notices.append(status)
            remaining = budget - captured
            if remaining <= 0:
                done.set()
                return
            chunk = indata if len(indata) <= remaining else indata[:remaining]
            frames.append(chunk.copy())
            captured += len(chunk)
            if captured >= budget:
                done.set()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
            done.set()

    say(f"Microfone: {info['name']} | mono int16 | {config.sample_rate} Hz")
    try:
        stream = sd.InputStream(
            device=device, samplerate=config.sample_rate,
            channels=1, dtype="int16", callback=_callback,
        )
    except Exception as exc:  # noqa: BLE001
        raise MicError(f"Não deu para criar o stream: {exc}") from exc

    try:
        with stream:
            deadline = time.monotonic() + config.max_seconds
            say("Gravando… Enter para parar; o limite encerra automaticamente.")
            if input_fn is not None and not done.is_set():
                input_fn("")
            elif input_fn is None:
                while not done.is_set():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or _terminal_stop(min(0.05, remaining)):
                        break
                    if not stream.active and not done.is_set():
                        raise MicError("Stream de entrada interrompido durante a gravação.")
    except MicError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MicError(f"Falha durante a captura: {exc}") from exc
    finally:
        done.set()
        pending_error = sys.exc_info()[0] is not None
        try:
            stream.close()
        except Exception as exc:  # noqa: BLE001
            if not pending_error:
                raise MicError(f"Não deu para liberar o stream: {exc}") from exc

    if errors:
        raise MicError(f"Falha no callback de áudio: {errors[0]}")
    for notice in notices:
        say(f"Aviso da captura: {notice}")
    if captured >= budget or time.monotonic() >= deadline:
        say(f"Limite de gravação ({config.max_seconds}s) atingido; captura encerrada.")
    if not frames:
        raise MicError("Nenhum áudio capturado.")

    import numpy as np

    path = None
    try:
        audio = np.concatenate(frames, axis=0)
        path = _temp_wav()
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(config.sample_rate)
            wav.writeframes(audio.tobytes())
    except BaseException as exc:
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                exc.add_note(f"Não deu para remover o WAV parcial: {cleanup_error}")
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise MicError(f"Não deu para salvar o áudio: {exc}") from exc
    return path


def _temp_wav() -> Path:
    """Cria WAV temporário com descritor fechado."""
    fd, name = tempfile.mkstemp(prefix="yby-mic-", suffix=".wav")
    os.close(fd)
    return Path(name)
