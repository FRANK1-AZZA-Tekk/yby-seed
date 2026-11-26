"""Backends assíncronos de STT (Whisper.cpp) e TTS (Kokoro-82M) em CPU."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Protocol, runtime_checkable

from src.yby.audio.device import CommandRunner, SubprocessCommandRunner


class AudioBackendError(RuntimeError):
    """Falha recuperável na camada local de STT ou TTS."""


@runtime_checkable
class STTBackend(Protocol):
    async def transcribe(self, wav_bytes: bytes, *, language: str = "pt") -> str: ...


@runtime_checkable
class TTSBackend(Protocol):
    async def synthesize(self, text: str, *, voice: str = "pf_dora") -> bytes: ...


class WhisperCppBackend:
    """Adapter não-bloqueante para `whisper-cli` (Whisper.cpp em CPU por padrão)."""

    def __init__(
        self,
        *,
        binary: str = "whisper-cli",
        model_path: str = "",
        threads: int = 4,
        runner: CommandRunner | None = None,
    ) -> None:
        self.binary = binary
        self.model_path = model_path
        self.threads = max(1, threads)
        self._runner = runner or SubprocessCommandRunner()

    async def transcribe(self, wav_bytes: bytes, *, language: str = "pt") -> str:
        if not wav_bytes:
            raise AudioBackendError("áudio vazio recebido para transcrição")
        if not self.model_path:
            raise AudioBackendError("YBY_WHISPER_CPP_MODEL não configurado")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = Path(tmp.name)
            wav_path.write_bytes(wav_bytes)

        try:
            cmd = [
                self.binary,
                "-m",
                self.model_path,
                "-f",
                str(wav_path),
                "-l",
                language,
                "-t",
                str(self.threads),
                "--no-timestamps",
            ]
            try:
                code, stdout, stderr = await self._runner.run(cmd)
            except FileNotFoundError as exc:
                raise AudioBackendError(
                    f"binário Whisper.cpp não encontrado: {self.binary}"
                ) from exc
            if code != 0:
                detail = stderr.decode("utf-8", errors="replace").strip()
                raise AudioBackendError(f"Whisper.cpp falhou (exit {code}): {detail}")
            transcript = stdout.decode("utf-8", errors="replace").strip()
            if not transcript:
                raise AudioBackendError("Whisper.cpp retornou transcrição vazia")
            return transcript
        finally:
            wav_path.unlink(missing_ok=True)


class KokoroTTSBackend:
    """Adapter não-bloqueante para `kokoro-tts` (Kokoro-82M em CPU por padrão)."""

    def __init__(
        self,
        *,
        binary: str = "kokoro-tts",
        default_voice: str = "pf_dora",
        runner: CommandRunner | None = None,
    ) -> None:
        self.binary = binary
        self.default_voice = default_voice
        self._runner = runner or SubprocessCommandRunner()

    async def synthesize(self, text: str, *, voice: str | None = None) -> bytes:
        clean = text.strip()
        if not clean:
            raise AudioBackendError("texto vazio para síntese Kokoro-82M")

        chosen_voice = voice or self.default_voice
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = Path(tmp.name)

        try:
            cmd = [
                self.binary,
                "--voice",
                chosen_voice,
                "--output",
                str(out_path),
            ]
            try:
                code, stdout, stderr = await self._runner.run(
                    cmd,
                    stdin_bytes=clean.encode("utf-8"),
                )
            except FileNotFoundError as exc:
                raise AudioBackendError(
                    f"binário Kokoro-82M não encontrado: {self.binary}"
                ) from exc
            if code != 0:
                detail = stderr.decode("utf-8", errors="replace").strip()
                raise AudioBackendError(f"Kokoro-82M falhou (exit {code}): {detail}")
            if out_path.exists() and out_path.stat().st_size > 0:
                return out_path.read_bytes()
            if stdout:
                return stdout
            raise AudioBackendError("Kokoro-82M não gerou áudio WAV")
        finally:
            out_path.unlink(missing_ok=True)
