"""PR-A: revisão de robustez — core / engine / agent_loop (pós #113)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from src.agent_loop.loop import ControlledAgentLoop
from src.agent_loop.planner import ScriptedPlanner
from src.agent_loop.tools import ToolRegistry, ToolSpec
from src.core.ollama_client import OllamaClient, OllamaClientError
from src.engine.providers import CascadingCloudProvider, CloudProvider, OllamaProvider
from tests.test_ollama_client import _Session
from tests.test_providers import _Resp, _Session as ProviderSession


class _BoomArgs(BaseModel):
    msg: str = Field(min_length=1)


def _boom_handler(_args: BaseModel) -> dict[str, object]:
    raise RuntimeError("tool interna falhou")


def test_tool_runtime_exception_stops_without_propagating() -> None:
    registry = ToolRegistry(approve=lambda _request: True)
    registry.register(
        ToolSpec(
            name="boom",
            description="levanta RuntimeError",
            args_model=_BoomArgs,
            handler=_boom_handler,
        )
    )
    loop = ControlledAgentLoop(
        registry=registry,
        planner=ScriptedPlanner(
            [{"action": "tool", "name": "boom", "arguments": {"msg": "x"}}]
        ),
        max_iterations=2,
    )
    result = loop.run("falha interna")
    assert result.status == "error"
    assert result.steps[-1].error == "tool interna falhou"


def test_cascading_cloud_close_encerra_primario_e_fallback() -> None:
    primary = ProviderSession(_Resp(200, {"choices": [{"message": {"content": "ok"}}]}))
    primary.closed = False
    primary.close = lambda: setattr(primary, "closed", True)  # type: ignore[method-assign]
    fallback = ProviderSession(_Resp(200, {"choices": [{"message": {"content": "ok"}}]}))
    fallback.closed = False
    fallback.close = lambda: setattr(fallback, "closed", True)  # type: ignore[method-assign]

    cascade = CascadingCloudProvider(
        CloudProvider("https://openrouter.ai/api/v1", api_key="k", timeout=1, session=primary),
        primary_model="m",
        primary_label="openrouter",
        fallback=CloudProvider("https://api.x.ai/v1", api_key="k2", timeout=1, session=fallback),
        fallback_model="grok",
        fallback_label="grok",
    )
    cascade.close()
    assert primary.closed is True
    assert fallback.closed is True


def test_ollama_client_chat_raises_on_connection_error() -> None:
    client = OllamaClient()
    client.session = _Session(error=ConnectionError("down"))  # type: ignore[assignment]
    with pytest.raises(OllamaClientError, match="chat falhou"):
        client.chat("qwen2.5-coder:3b", [{"role": "user", "content": "oi"}])


def test_ollama_provider_close_idempotente() -> None:
    http = ProviderSession(_Resp(200, {"response": "ok"}))
    provider = OllamaProvider("http://127.0.0.1:11434", timeout=1, session=http)
    provider.close()
    provider.close()