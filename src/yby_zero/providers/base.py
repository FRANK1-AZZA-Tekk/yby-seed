from collections.abc import AsyncIterator
from typing import Protocol


class LLMProvider(Protocol):
    async def generate(self, text: str) -> str: ...

    async def stream(self, text: str) -> AsyncIterator[str]: ...


class STTProvider(Protocol):
    async def transcribe(self, audio: bytes) -> str: ...


class TTSProvider(Protocol):
    async def synthesize(self, text: str) -> bytes: ...
