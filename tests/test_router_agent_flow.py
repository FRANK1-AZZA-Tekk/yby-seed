"""Fluxo ponta a ponta do OfflineRouter (sem Ollama/nuvem)."""

from __future__ import annotations

from pathlib import Path

from src.agent_loop.planner import ScriptedPlanner
from src.router.integration import temp_vault_with_note
from src.router.observability import RouterObserver
from src.router.registry import ModelEntry, ModelRegistry
from src.router.router import OfflineRouter


def _finish(answer: dict) -> ScriptedPlanner:
    return ScriptedPlanner([{"action": "finish", "answer": answer}])


def test_route_general() -> None:
    router = OfflineRouter(observer=RouterObserver())
    result = router.handle("olá, tudo bem?", planner=_finish({"kind": "general"}))
    assert result.decision.intent == "general"
    assert result.status == "ok"
    assert result.decision.constraints.allow_cloud is False
    assert result.fallback_used is False
    assert router.observer.events[-1].intent == "general"


def test_route_coding() -> None:
    router = OfflineRouter()
    result = router.handle(
        "corrija o bug nesta função python",
        planner=_finish({"kind": "coding"}),
    )
    assert result.decision.intent == "coding"
    assert "coder" in result.decision.selected_profile or result.decision.selected_model


def test_route_knowledge_with_sources(tmp_path: Path) -> None:
    vault = temp_vault_with_note(
        tmp_path / "vault",
        "docs",
        "O vault guarda notas Markdown locais do YBY.",
    )
    router = OfflineRouter(vault=vault)
    result = router.handle(
        "explique o que é o vault do YBY",
        planner=_finish({"kind": "knowledge"}),
    )
    assert result.decision.intent == "knowledge"
    assert result.sources
    assert all("name" in src for src in result.sources)


def test_route_automation_requires_approval() -> None:
    router = OfflineRouter()
    blocked = router.handle(
        "automatizar instalação com script",
        approved=False,
        planner=_finish({"kind": "auto"}),
    )
    assert blocked.decision.intent == "automation"
    assert blocked.status == "blocked"
    assert blocked.approved is False

    ok = router.handle(
        "automatizar instalação com script",
        approved=True,
        planner=ScriptedPlanner(
            [
                {"action": "tool", "name": "echo_json", "arguments": {"message": "ok"}},
                {"action": "finish", "answer": {"done": True}},
            ]
        ),
    )
    assert ok.status == "ok"
    assert ok.tools_used == ["echo_json"]
    assert ok.decision.requires_approval is True


def test_fallback_when_primary_fails() -> None:
    calls: list[str] = []

    def invoker(entry: ModelEntry, prompt: str) -> str:
        calls.append(entry.model)
        if entry.role != "fallback":
            raise RuntimeError("primary offline")
        return "resposta-fallback"

    router = OfflineRouter(invoker=invoker, max_fallback_retries=0)
    result = router.handle("olá", planner=_finish({"via": "fb"}))
    assert result.fallback_used is True
    assert result.fallback_model == "qwen3-4b-instruct"
    assert result.selected_model == "qwen3-4b-instruct"
    assert result.status == "ok"
    assert "qwen3-8b-instruct" in calls
    assert "qwen3-4b-instruct" in calls
    event = router.observer.events[-1]
    assert event.fallback_used is True
    assert event.outcome == "fallback_success"


def test_structured_logs_without_secrets() -> None:
    observer = RouterObserver()
    router = OfflineRouter(observer=observer)
    result = router.handle("implemente um teste pytest", planner=_finish({"t": 1}))
    payload = observer.events[-1].to_dict()
    assert payload["request_id"] == result.request_id
    assert "selected_model" in payload
    assert "latency_ms" in payload
    assert "tokens" in payload
    assert "cost" in payload
    assert "approval_required" in payload
    assert "outcome" in payload
    dumped = str(payload)
    assert "api_key" not in dumped
    assert "password" not in dumped


def test_safety_limits_on_response() -> None:
    router = OfflineRouter()
    result = router.handle("bom dia", planner=_finish({"ok": True}))
    assert result.decision.constraints.max_steps >= 1
    assert result.decision.constraints.max_tool_calls <= result.decision.constraints.max_steps
    assert result.decision.constraints.allow_cloud is False
    assert result.to_dict()["allow_cloud"] is False


def test_registry_used_for_coding_model() -> None:
    registry = ModelRegistry.default()
    router = OfflineRouter(model_registry=registry)
    result = router.handle("refatore código typescript", planner=_finish({"c": 1}))
    assert result.decision.intent == "coding"
    assert registry.primary_for_intent("coding").model == result.decision.selected_model
