"""TTS local com Piper (binário no PATH). Import/subprocess lazy."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.voice.config import VoiceConfig


class TtsError(RuntimeError):
    """Falha ao sintetizar ou reproduzir áudio."""


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
    """Sintetiza e reproduz; no sucesso o chamador deve remover o WAV.

    Em falha ou cancelamento, tenta remover o arquivo antes de propagar o erro.
    Player ausente ou com retorno não zero é falha, não sucesso silencioso.
    """
    cleaned = text.strip()
    if not cleaned:
        raise TtsError("Texto vazio; nada para falar.")

    ok, message = check_tts(config)
    if not ok:
        raise TtsError(message)

    try:
        out = _temp_wav()
    except OSError as exc:
        raise TtsError(f"Não deu para criar o WAV temporário: {exc}") from exc

    try:
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
        except subprocess.TimeoutExpired as exc:
            raise TtsError("Piper demorou demais.") from exc
        except OSError as exc:
            raise TtsError(f"Não deu para executar o Piper: {exc}") from exc

        if proc.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
            err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
            raise TtsError(err or "Piper não gerou áudio.")

        _play(out, config)
        return out
    except BaseException as exc:
        try:
            out.unlink(missing_ok=True)
        except OSError as cleanup_error:
            exc.add_note(f"Não deu para remover o WAV temporário: {cleanup_error}")
        if isinstance(exc, OSError):
            raise TtsError(f"Falha ao acessar o WAV: {exc}") from exc
        raise


def _temp_wav() -> Path:
    """WAV temporário. `mkstemp` devolve um fd que precisa ser fechado."""

    fd, name = tempfile.mkstemp(prefix="yby-tts-", suffix=".wav")
    os.close(fd)
    return Path(name)


def _play(wav_path: Path, config: VoiceConfig) -> None:
    """Reproduz o WAV ou levanta TtsError com a causa da falha."""
    try:
        player = shutil.which(config.play_bin)
        if player is None:
            raise TtsError(f"Player '{config.play_bin}' não encontrado no PATH.")
        proc = subprocess.run(
            [player, str(wav_path)],
            capture_output=True,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise TtsError("Reprodução de áudio demorou demais.") from exc
    except OSError as exc:
        raise TtsError(f"Não deu para executar o player: {exc}") from exc
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise TtsError(f"Player falhou (código {proc.returncode}): {err or 'sem detalhes'}")
