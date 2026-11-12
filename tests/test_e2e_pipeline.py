"""E2E determinístico: HTTP generate → RAG → agentes → sandbox → dataset → MQTT → gpu_gate."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.yby_seed.agents.roles import ArchitectAgent, AuditorAgent, BuilderAgent
from src.yby_seed.agents.state import MissionState
from src.yby_seed.config import Settings
from src.yby_seed.main import app
from src.yby_seed.models import StructuredCode
from src.yby_seed.runtime.gpu_gate import inference_slot as real_inference_slot
from src.yby_seed.sandbox import ValidationResult


@pytest.fixture
def code_artifact() -> StructuredCode:
    return StructuredCode(
        language="python",
        filename="main.py",
        code="def add(a, b):\n    return a + b\n",
        tests="def test_add():\n    assert add(1, 2) == 3\n",
    )


def test_e2e_seed_generate_pipeline(
    tmp_path,
    code_artifact: StructuredCode,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset_path = tmp_path / "validated_pairs.jsonl"

    def settings_with_dataset() -> Settings:
        base = Settings()
        return base.model_copy(update={"datasets_path": dataset_path})

    for target in (
        "src.yby_seed.config.get_settings",
        "src.yby_seed.engine.get_settings",
        "src.yby_seed.agents.orchestrator.get_settings",
    ):
        monkeypatch.setattr(target, settings_with_dataset)

    rag_calls: list[str] = []

    async def fake_fetch_context(query: str, domain: str | None = None, top_k: int = 4) -> str:
        rag_calls.append(f"{domain}:{query[:20]}")
        return "[yby_arch:doc.md]\ncontexto pgvector mockado"

    async def architect_side_effect(state: MissionState) -> MissionState:
        from src.yby_seed.agents.roles import DOMAIN_RAG

        domain = DOMAIN_RAG.get(state.domain, "yby_arch")
        state.rag_context = await fake_fetch_context(state.user_intent, domain)
        state.architecture_plan = {"steps": [{"id": 1, "action": "implementar"}]}
        state.gpio_manifest = {"pins": []}
        return state

    async def builder_side_effect(state: MissionState) -> MissionState:
        state.generated_code = code_artifact
        return state

    async def auditor_side_effect(state: MissionState) -> MissionState:
        state.auditor_guidance = "Causa: typo\nGuia: corrigir sintaxe"
        return state

    validation_calls = {"n": 0}

    def validation_side_effect(**_kwargs):
        validation_calls["n"] += 1
        if validation_calls["n"] == 1:
            return ValidationResult(False, "", "SyntaxError: invalid syntax", {})
        return ValidationResult(True, "ok", "", {"docker": {"ok": True}})

    mqtt_payloads: list[str] = []

    def capture_mqtt(settings, request, artifact) -> bool:
        mqtt_payloads.append(
            json.dumps(
                {"prompt": request.prompt, "filename": artifact.filename},
                ensure_ascii=False,
            )
        )
        return True

    slot_events: list[str] = []

    @asynccontextmanager
    async def tracking_inference_slot():
        slot_events.append("acquire")
        async with real_inference_slot():
            yield
        slot_events.append("release")

    with (
        patch(
            "src.yby_seed.agents.roles.fetch_context", new=AsyncMock(side_effect=fake_fetch_context)
        ),
        patch.object(ArchitectAgent, "run", AsyncMock(side_effect=architect_side_effect)),
        patch.object(BuilderAgent, "run", AsyncMock(side_effect=builder_side_effect)),
        patch.object(AuditorAgent, "run", AsyncMock(side_effect=auditor_side_effect)),
        patch(
            "src.yby_seed.agents.orchestrator.execute_validated",
            side_effect=validation_side_effect,
        ),
        patch("src.yby_seed.agents.orchestrator.publish_validated_code", side_effect=capture_mqtt),
        patch("src.yby_seed.engine.inference_slot", tracking_inference_slot),
        patch("src.yby_seed.daemon.mqtt_listener.MqttAutonomyWorker.start", new=AsyncMock()),
        patch("src.yby_seed.daemon.mqtt_listener.MqttAutonomyWorker.stop", new=AsyncMock()),
        patch("src.yby_seed.runtime.resources.open_pg_pool", new=AsyncMock(return_value=None)),
        patch("src.yby_seed.runtime.resources.shutdown", new=AsyncMock()),
    ):
        with TestClient(app) as client:
            response = client.post(
                "/v1/seed/generate",
                json={"prompt": "criar função add", "domain": "python_fastapi"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["attempts"] >= 2
    assert validation_calls["n"] == 2
    assert rag_calls
    assert mqtt_payloads
    assert body.get("dataset_saved") is True
    assert dataset_path.is_file()
    lines = dataset_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["messages"][1]["content"] == "criar função add"
    assert "acquire" in slot_events and "release" in slot_events
