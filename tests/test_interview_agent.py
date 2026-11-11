"""Testes do InterviewAgent (OllamaClient + JSON)."""

import pytest
from src.agents.interview_agent import InterviewAgent
from src.core.ollama_client import OllamaError


class FakeOllama:
    def __init__(self, text: str):
        self.text = text
        self.calls: list[dict] = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.text

    def close(self):
        pass


@pytest.mark.asyncio
async def test_basic_com_fence_json():
    raw = '```json\n{"intent": "backup_automation", "slots": {}, "confidence": 0.9}\n```'
    agent = InterviewAgent(ollama=FakeOllama(raw))  # type: ignore[arg-type]
    result = await agent.interview("faça backup", mode="basic")
    assert result["intent"] == "backup_automation"
    assert agent.ollama.calls[0].get("format") is not None


@pytest.mark.asyncio
async def test_junior_exige_answers():
    raw = '{"intent": "backup_automation", "slots": {}, "confidence": 0.9}'
    agent = InterviewAgent(ollama=FakeOllama(raw))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="answers"):
        await agent.interview("backup", mode="junior")


@pytest.mark.asyncio
async def test_junior_com_answers():
    raw = '{"intent": "backup_automation", "slots": {"source": null}, "confidence": 0.9}'
    agent = InterviewAgent(ollama=FakeOllama(raw))  # type: ignore[arg-type]
    result = await agent.interview(
        "backup",
        mode="junior",
        answers=["~/docs", "/mnt/backup", "diario", "ZIP"],
    )
    assert result["mode"] == "junior"
    assert "resumo" in result
    assert len(result["answers"]) == 4


@pytest.mark.asyncio
async def test_ollama_error_basic():
    class Boom:
        def generate(self, **kwargs):
            raise OllamaError("down")

        def close(self):
            pass

    agent = InterviewAgent(ollama=Boom())  # type: ignore[arg-type]
    result = await agent.interview("oi", mode="basic")
    assert result["intent"] == "ollama_unavailable"
