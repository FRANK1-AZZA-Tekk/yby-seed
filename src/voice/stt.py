"""STT local com faster-whisper. Import lazy — CI não precisa do pacote."""

from __future__ import annotations

from pathlib import Path

from src.voice.config import VoiceConfig


class SttError(RuntimeError):
    """Falha ao transcrever ou dependência ausente."""


def check_stt() -> tuple[bool, str]:
    """Retorna (ok, mensagem). Não baixa modelos."""

    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return (
            False,
            "faster-whisper não instalado. Rode: pip install -r requirements-voice.txt",
        )
    return True, "faster-whisper disponível"


def transcribe(audio_path: Path, config: VoiceConfig) -> str:
    """Transcreve um WAV/PCM. Levanta SttError se o pacote ou o áudio falhar."""

    ok, message = check_stt()
    if not ok:
        raise SttError(message)

    from faster_whisper import WhisperModel

    path = Path(audio_path)
    if not path.is_file():
        raise SttError(f"Arquivo de áudio não encontrado: {path}")

    try:
        model = WhisperModel(
            config.whisper_model,
            device=config.whisper_device,
            compute_type=config.whisper_compute_type,
        )
        segments, _info = model.transcribe(str(path), language="pt")
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
    except Exception as exc:  # noqa: BLE001 — superfície clara para o CLI
        raise SttError(f"Transcrição falhou: {exc}") from exc

    if not text.strip():
        raise SttError("Não deu para entender o áudio. Tente de novo.")
    return text.strip()
