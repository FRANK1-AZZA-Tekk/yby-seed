"""Adaptador assíncrono PipeWire/PulseAudio para o Baseus Bowie MC2 Air (HFP/A2DP)."""

from __future__ import annotations

import asyncio
import math
import struct
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from src.yby.audio.schemas import BluetoothProfile


@runtime_checkable
class CommandRunner(Protocol):
    async def run(
        self,
        argv: Sequence[str],
        *,
        stdin_bytes: bytes | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, bytes, bytes]: ...


class SubprocessCommandRunner:
    """Executa binários externos sem bloquear o event loop."""

    async def run(
        self,
        argv: Sequence[str],
        *,
        stdin_bytes: bytes | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, bytes, bytes]:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE if stdin_bytes is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=stdin_bytes),
                timeout=timeout,
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise
        return int(proc.returncode or 0), stdout, stderr


def has_voice_activity(pcm16_bytes: bytes, *, rms_threshold: float = 300.0) -> bool:
    """Detector de atividade de voz (VAD) simples baseado em RMS para PCM16 mono."""

    sample_count = len(pcm16_bytes) // 2
    if sample_count == 0:
        return False
    samples = struct.unpack(f"<{sample_count}h", pcm16_bytes[: sample_count * 2])
    mean_sq = sum(sample * sample for sample in samples) / sample_count
    return math.sqrt(mean_sq) >= rms_threshold


@runtime_checkable
class AudioDeviceAdapter(Protocol):
    device_name: str

    async def detect_device(self) -> str | None: ...

    async def set_profile(self, profile: BluetoothProfile) -> bool: ...

    async def record_utterance(
        self,
        *,
        max_seconds: float = 10.0,
        sample_rate: int = 16_000,
    ) -> bytes: ...

    async def play_wav(self, wav_bytes: bytes) -> None: ...


class PipeWireBluetoothDevice:
    """Controla captura HFP e reprodução A2DP via PipeWire/pactl sem bloquear."""

    _PROFILE_MAP: dict[BluetoothProfile, str] = {
        "hfp": "headset-head-unit",
        "a2dp": "a2dp-sink",
    }

    def __init__(
        self,
        device_name: str = "Baseus Bowie MC2 Air",
        *,
        runner: CommandRunner | None = None,
        pactl_bin: str = "pactl",
        record_bin: str = "pw-record",
        play_bin: str = "pw-play",
    ) -> None:
        self.device_name = device_name
        self._runner = runner or SubprocessCommandRunner()
        self._pactl_bin = pactl_bin
        self._record_bin = record_bin
        self._play_bin = play_bin
        self._cached_card: str | None = None

    async def detect_device(self) -> str | None:
        """Procura o card Bluetooth correspondente ao Baseus Bowie MC2 Air no PipeWire."""

        try:
            code, stdout, _ = await self._runner.run([self._pactl_bin, "list", "cards", "short"])
        except FileNotFoundError:
            return None
        if code != 0:
            return None

        needle = self.device_name.casefold().replace(" ", "_")
        name_words = [w for w in self.device_name.casefold().split() if w]
        for line in stdout.decode("utf-8", errors="replace").splitlines():
            cols = line.split("\t")
            if len(cols) < 2:
                continue
            card_name = cols[1].strip()
            folded = card_name.casefold()
            if needle in folded or all(word in folded for word in name_words[:2]):
                self._cached_card = card_name
                return card_name
            if "bluez_card" in folded and "baseus" in folded:
                self._cached_card = card_name
                return card_name
        return None

    async def set_profile(self, profile: BluetoothProfile) -> bool:
        card = self._cached_card or await self.detect_device()
        if not card:
            return False
        pw_profile = self._PROFILE_MAP[profile]
        try:
            code, _, _ = await self._runner.run(
                [self._pactl_bin, "set-card-profile", card, pw_profile]
            )
        except FileNotFoundError:
            return False
        return code == 0

    async def record_utterance(
        self,
        *,
        max_seconds: float = 10.0,
        sample_rate: int = 16_000,
    ) -> bytes:
        if max_seconds <= 0:
            raise ValueError("max_seconds deve ser > 0.")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = Path(tmp.name)
        try:
            try:
                code, _, stderr = await self._runner.run(
                    [
                        self._record_bin,
                        "--rate",
                        str(sample_rate),
                        "--channels",
                        "1",
                        "--format",
                        "s16",
                        str(wav_path),
                    ],
                    timeout=max_seconds,
                )
            except TimeoutError:
                if wav_path.exists() and wav_path.stat().st_size > 0:
                    return wav_path.read_bytes()
                raise
            if code != 0 and (not wav_path.exists() or wav_path.stat().st_size == 0):
                raise RuntimeError(stderr.decode("utf-8", errors="replace").strip())
            return wav_path.read_bytes() if wav_path.exists() else b""
        finally:
            wav_path.unlink(missing_ok=True)

    async def play_wav(self, wav_bytes: bytes) -> None:
        if not wav_bytes:
            return
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = Path(tmp.name)
            wav_path.write_bytes(wav_bytes)
        try:
            code, _, stderr = await self._runner.run([self._play_bin, str(wav_path)])
            if code != 0:
                raise RuntimeError(stderr.decode("utf-8", errors="replace").strip())
        finally:
            wav_path.unlink(missing_ok=True)
