"""Orquestra gravar → transcrever → ask → falar."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.engine.hybrid import EngineReply, HybridEngine
from src.voice.config import VoiceConfig
from src.voice.mic import MicError, check_mic, record_until_enter
from src.voice.stt import SttError, check_stt, transcribe
from src.voice.tts import TtsError, check_tts, speak


class VoiceError(RuntimeError):
    """Camada de voz indisponível ou falha no fluxo."""


@dataclass(frozen=True)
class VoiceTurn:
    """Um turno completo de voz."""

    transcript: str
    reply: EngineReply
    tts_path: Path | None
    tts_notice: str | None


def availability(config: VoiceConfig) -> tuple[bool, str]:
    """Checa mic + STT. TTS é opcional (degrada para só texto)."""

    parts: list[str] = []
    ok_mic, msg_mic = check_mic()
    ok_stt, msg_stt = check_stt()
    ok_tts, msg_tts = check_tts(config)
    if not ok_mic:
        parts.append(msg_mic)
    if not ok_stt:
        parts.append(msg_stt)
    if not ok_tts:
        parts.append(f"(TTS opcional) {msg_tts}")
    if not ok_mic or not ok_stt:
        return False, " ".join(parts)
    if parts:
        return True, " ".join(parts)
    return True, "voz pronta"


def listen_once(
    engine: HybridEngine,
    config: VoiceConfig,
    *,
    explicit_heavy: bool = False,
    speak_reply: bool = True,
    input_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], None] | None = None,
) -> VoiceTurn:
    """Push-to-talk: grava até Enter, pergunta ao motor, opcionalmente fala a resposta."""

    ok, message = availability(config)
    if not ok:
        raise VoiceError(message)

    say = output_fn or (lambda _msg: None)
    try:
        wav = record_until_enter(config, input_fn=input_fn, output_fn=output_fn)
    except MicError as exc:
        raise VoiceError(str(exc)) from exc

    try:
        try:
            transcript = transcribe(wav, config)
        except SttError as exc:
            raise VoiceError(str(exc)) from exc
        finally:
            wav.unlink(missing_ok=True)

        say(f"você: {transcript}")
        reply = engine.reply(transcript, explicit_heavy=explicit_heavy)

        tts_path: Path | None = None
        tts_notice: str | None = None
        if speak_reply and reply.provider != "none" and reply.text.strip():
            try:
                tts_path = speak(reply.text, config)
            except TtsError as exc:
                tts_notice = str(exc)
                say(f"TTS indisponível: {exc}")

        return VoiceTurn(transcript, reply, tts_path, tts_notice)
    except VoiceError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise VoiceError(str(exc)) from exc
