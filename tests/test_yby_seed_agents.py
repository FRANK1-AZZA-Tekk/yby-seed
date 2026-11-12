from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.yby_seed.agents.orchestrator import MissionOrchestrator
from src.yby_seed.agents.roles import ArchitectAgent, BuilderAgent, _approx_tokens
from src.yby_seed.agents.state import MissionState
from src.yby_seed.models import GenerateRequest, StructuredCode


def test_approx_tokens() -> None:
    assert _approx_tokens("abcd") >= 1


@pytest.mark.asyncio
async def test_orchestrator_success_flow() -> None:
    code = StructuredCode(
        language="python",
        filename="main.py",
        code="def add(a, b):\n    return a + b\n",
        tests="def test_add():\n    assert add(1, 2) == 3\n",
    )

    async def architect_side_effect(state: MissionState) -> MissionState:
        state.architecture_plan = {"steps": [{"id": 1, "action": "implementar soma"}]}
        state.gpio_manifest = {"pins": []}
        state.rag_context = "ctx"
        return state

    async def builder_side_effect(state: MissionState) -> MissionState:
        state.generated_code = code
        return state

    orchestrator = MissionOrchestrator()
    with (
        patch.object(ArchitectAgent, "run", AsyncMock(side_effect=architect_side_effect)),
        patch.object(BuilderAgent, "run", AsyncMock(side_effect=builder_side_effect)),
        patch(
            "src.yby_seed.agents.orchestrator.execute_validated",
            return_value=(True, "ok", ""),
        ),
        patch("src.yby_seed.agents.orchestrator.append_dataset", return_value=True),
        patch("src.yby_seed.agents.orchestrator.publish_validated_code", return_value=True),
    ):
        response = await orchestrator.run(
            GenerateRequest(prompt="criar função de soma", domain="python_fastapi")
        )

    assert response.success is True
    assert response.code is not None
    assert "add" in response.code


@pytest.mark.asyncio
async def test_architect_picks_cloud_model_on_large_context() -> None:
    client = MagicMock()
    agent = ArchitectAgent(client)
    huge = "x" * 7000
    assert agent._model_for_context(huge, huge) == "yby-cloud-coder"
