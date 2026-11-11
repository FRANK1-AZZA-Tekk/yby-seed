"""TTS local com Piper (binário no PATH). Import/subprocess lazy."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from src.voice.config import VoiceConfig


class TtsError(RuntimeError):
    """Falha ao sintetizar ou dependência ausente."""


def check_tts(config: VoiceConfig) -> tuple[bool, str]:
    """Retorna (ok, mensagem) sem sintetizar."""

    if shutil.which(config.piper_bin) is None:
        return (
            False,
            (
                f"Binário '{config.piper_bin}' não encontrado no PATH. "
                "Instale o Piper e defina YBY_PIPER_MODEL com o .onnx da voz."
            ),
        )
    if not config.piper_model:
        return (
            False,
            "YBY_PIPER_MODEL não definida. Aponta para o arquivo .onnx da voz Piper.",
        )
    model = Path(config.piper_model)
    if not model.is_file():
        return False, f"Modelo Piper não encontrado: {model}"
    return True, "Piper disponível"


def speak(text: str, config: VoiceConfig) -> Path:
    """Sintetiza `text` em WAV temporário e tenta tocar. Retorna o caminho do WAV."""

    cleaned = text.strip()
    if not cleaned:
        raise TtsError("Texto vazio; nada para falar.")

    ok, message = check_tts(config)
    if not ok:
        raise TtsError(message)

    out = Path(tempfile.mkstemp(prefix="yby-tts-", suffix=".wav")[1])
    try:
        proc = subprocess.run(
            [
                config.piper_bin,
                "--model",
                config.piper_model,
                "--output_file",
                str(out),
            ],
            input=cleaned.encode("utf-8"),
            capture_output=True,
            check=False,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise TtsError(message) from exc
    except subprocess.TimeoutExpired as exc:
        out.unlink(missing_ok=True)
        raise TtsError("Piper demorou demais.") from exc

    if proc.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        out.unlink(missing_ok=True)
        raise TtsError(err or "Piper não gerou áudio.")

    _play(out, config)
    return out


def _play(wav_path: Path, config: VoiceConfig) -> None:
    """Toca o WAV se houver player; senão só deixa o arquivo."""

    player = shutil.which(config.play_bin)
    if player is None:
        return
    subprocess.run(
        [player, str(wav_path)],
        capture_output=True,
        check=False,
        timeout=120,
    )
