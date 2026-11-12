import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.yby_seed.agents.orchestrator import MissionOrchestrator
from src.yby_seed.agents.roles import ArchitectAgent, BuilderAgent
from src.yby_seed.agents.state import MissionState
from src.yby_seed.models import GenerateRequest, StructuredCode
from src.yby_seed.sandbox import ValidationResult


@pytest.mark.asyncio
async def test_orchestrator_success_flow() -> None:
    code = StructuredCode(
        language="python",
        filename="main.py",
        code="def add(a, b):\n    return a + b\n",
        tests="def test_add():\n    assert add(1, 2) == 3\n",
    )

    async def architect_side_effect(state: MissionState) -> MissionState:
        state.architecture_plan = {"steps": [{"id": 1, "action": "soma"}]}
        state.gpio_manifest = {"pins": []}
        return state

    calls = {"n": 0}

    async def builder_side_effect(state: MissionState) -> MissionState:
        calls["n"] += 1
        state.generated_code = code
        return state

    orchestrator = MissionOrchestrator()
    with (
        patch.object(ArchitectAgent, "run", AsyncMock(side_effect=architect_side_effect)),
        patch.object(BuilderAgent, "run", AsyncMock(side_effect=builder_side_effect)),
        patch(
            "src.yby_seed.agents.orchestrator.execute_validated",
            return_value=ValidationResult(True, "ok", "", {}),
        ),
        patch("src.yby_seed.agents.orchestrator.append_dataset", return_value=True),
        patch("src.yby_seed.agents.orchestrator.publish_validated_code", return_value=True),
    ):
        response = await orchestrator.run(
            GenerateRequest(prompt="criar soma", domain="python_fastapi")
        )
    assert response.success is True
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_orchestrator_self_healing_after_sandbox_fail() -> None:
    code = StructuredCode(
        language="python",
        filename="main.py",
        code="def f():\n    return 1\n",
        tests="def test_f():\n    assert f()==1\n",
    )

    async def architect_side_effect(state: MissionState) -> MissionState:
        state.architecture_plan = {"steps": []}
        state.gpio_manifest = {"pins": []}
        return state

    async def builder_side_effect(state: MissionState) -> MissionState:
        state.generated_code = code
        return state

    validation_calls = {"n": 0}

    def validation_side_effect(**_kwargs):
        validation_calls["n"] += 1
        if validation_calls["n"] == 1:
            return ValidationResult(False, "", "compile error", {})
        return ValidationResult(True, "ok", "", {})

    orchestrator = MissionOrchestrator()
    with (
        patch.object(ArchitectAgent, "run", AsyncMock(side_effect=architect_side_effect)),
        patch.object(BuilderAgent, "run", AsyncMock(side_effect=builder_side_effect)),
        patch(
            "src.yby_seed.agents.orchestrator.execute_validated", side_effect=validation_side_effect
        ),
        patch("src.yby_seed.agents.orchestrator.append_dataset", return_value=True),
        patch("src.yby_seed.agents.orchestrator.publish_validated_code", return_value=True),
    ):
        response = await orchestrator.run(
            GenerateRequest(prompt="corrigir", domain="python_fastapi")
        )

    assert response.success is True
    assert response.attempts >= 2


@pytest.mark.asyncio
async def test_inference_slot_serializes_concurrent_generate() -> None:
    active = 0
    max_active = 0

    async def slow_generate(_request):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        active -= 1
        from src.yby_seed.models import GenerateResponse

        return GenerateResponse(success=True, attempts=1, code="x")

    from src.yby_seed.engine import SeedEngine

    engine = SeedEngine()
    with patch.object(engine._orchestrator, "run", side_effect=slow_generate):
        await asyncio.gather(
            engine.generate(GenerateRequest(prompt="a", domain="python_fastapi")),
            engine.generate(GenerateRequest(prompt="b", domain="python_fastapi")),
        )
    assert max_active == 1
