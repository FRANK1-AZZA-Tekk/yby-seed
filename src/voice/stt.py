"""STT local com faster-whisper. Import lazy — CI não precisa do pacote."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.voice.config import VoiceConfig

# Heurística conservadora: logprob médio muito baixo ⇒ ambíguo (assist --voice).
_AMBIGUOUS_LOGPROB = -1.2


class SttError(RuntimeError):
    """Falha ao transcrever ou dependência ausente."""


@dataclass(frozen=True)
class TranscriptResult:
    """Texto + sinal de confiança. `transcribe` continua devolvendo só o texto."""

    text: str
    avg_logprob: float | None = None

    @property
    def ambiguous(self) -> bool:
        return is_ambiguous_transcript(self.text, self.avg_logprob)


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


def is_ambiguous_transcript(text: str, avg_logprob: float | None = None) -> bool:
    """True se o texto é vazio/quase vazio ou a confiança é baixa."""

    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return True
    if len(cleaned) <= 1 and cleaned.casefold() not in {"s", "n", "y"}:
        return True
    if avg_logprob is not None and avg_logprob < _AMBIGUOUS_LOGPROB:
        return True
    return False


def transcribe_detailed(audio_path: Path, config: VoiceConfig) -> TranscriptResult:
    """Transcreve com média de logprob (quando o backend expõe)."""

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
        parts: list[str] = []
        logprobs: list[float] = []
        for segment in segments:
            if segment.text and segment.text.strip():
                parts.append(segment.text.strip())
            avg = getattr(segment, "avg_logprob", None)
            if isinstance(avg, (int, float)):
                logprobs.append(float(avg))
        text = " ".join(parts)
    except Exception as exc:  # noqa: BLE001 — superfície clara para o CLI
        raise SttError(f"Transcrição falhou: {exc}") from exc

    if not text.strip():
        raise SttError("Não deu para entender o áudio. Tente de novo.")
    avg = sum(logprobs) / len(logprobs) if logprobs else None
    return TranscriptResult(text=text.strip(), avg_logprob=avg)


def transcribe(audio_path: Path, config: VoiceConfig) -> str:
    """Transcreve um WAV/PCM. Levanta SttError se o pacote ou o áudio falhar.

    Contrato estável para `listen` / `ask --voice` — só o texto.
    """

    return transcribe_detailed(audio_path, config).text
