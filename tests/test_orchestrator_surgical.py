from unittest.mock import AsyncMock, patch

import pytest

from src.yby_seed.agents.orchestrator import MissionOrchestrator
from src.yby_seed.agents.roles import ArchitectAgent, AuditorAgent, BuilderAgent
from src.yby_seed.agents.state import MissionState
from src.yby_seed.models import GenerateRequest, StructuredCode
from src.yby_seed.sandbox import ValidationResult


@pytest.mark.asyncio
async def test_orchestrator_applies_surgical_blocks_on_retry() -> None:
    base_code = "def f():\n    return 1\n"
    patch_body = "<<<<<<< SEARCH\nreturn 1\n=======\nreturn 2\n>>>>>>> REPLACE\n"
    code_v1 = StructuredCode(language="python", filename="main.py", code=base_code, tests="")
    code_v2 = StructuredCode(language="python", filename="main.py", code=patch_body, tests="")

    async def architect_side_effect(state: MissionState) -> MissionState:
        state.architecture_plan = {"steps": []}
        state.gpio_manifest = {"pins": []}
        return state

    builder_calls = {"n": 0}

    async def builder_side_effect(state: MissionState) -> MissionState:
        builder_calls["n"] += 1
        state.generated_code = code_v2 if builder_calls["n"] >= 2 else code_v1
        return state

    validation_calls = {"n": 0}

    def validation_side_effect(**kwargs):
        validation_calls["n"] += 1
        if validation_calls["n"] == 1:
            return ValidationResult(False, "", "fail", {})
        assert "return 2" in kwargs.get("code", "")
        return ValidationResult(True, "ok", "", {})

    orchestrator = MissionOrchestrator()
    with (
        patch.object(ArchitectAgent, "run", AsyncMock(side_effect=architect_side_effect)),
        patch.object(BuilderAgent, "run", AsyncMock(side_effect=builder_side_effect)),
        patch.object(AuditorAgent, "run", AsyncMock(side_effect=lambda s: s)),
        patch(
            "src.yby_seed.agents.orchestrator.execute_validated", side_effect=validation_side_effect
        ),
        patch("src.yby_seed.agents.orchestrator.append_dataset", return_value=True),
        patch("src.yby_seed.agents.orchestrator.publish_validated_code", return_value=True),
    ):
        response = await orchestrator.run(GenerateRequest(prompt="patch", domain="python_fastapi"))

    assert response.success is True
    assert "return 2" in (response.code or "")
