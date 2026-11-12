"""Fachada do motor — delega ao orquestrador multiagente."""

from __future__ import annotations

from src.yby_seed.agents.orchestrator import MissionOrchestrator
from src.yby_seed.config import Settings, get_settings
from src.yby_seed.models import GenerateRequest, GenerateResponse


class SeedEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._orchestrator = MissionOrchestrator(settings=self.settings)

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        return await self._orchestrator.run(request)


async def generate_and_verify(request: GenerateRequest, **kwargs: object) -> GenerateResponse:
    settings = kwargs.get("settings")
    orchestrator = MissionOrchestrator(
        settings=settings if isinstance(settings, Settings) else None
    )
    return await orchestrator.run(request)
