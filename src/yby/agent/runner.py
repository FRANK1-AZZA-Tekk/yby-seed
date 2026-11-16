"""Cliente Ollama local para o agente (sem nuvem)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests

from src.engine.providers import OllamaProvider, ProviderError, build_ollama_generate_payload
from src.yby.agent.prompts import SYSTEM_PROMPT, build_planner_prompt
from src.yby.agent.schemas import AgentStep, parse_agent_step


DEFAULT_AGENT_MODEL = "qwen2.5:7b"
FALLBACK_AGENT_MODEL = "qwen3:8b"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_NUM_CTX = 8192


@dataclass(frozen=True)
class AgentOllamaConfig:
    base_url: str
    model: str
    temperature: float = DEFAULT_TEMPERATURE
    num_ctx: int = DEFAULT_NUM_CTX
    timeout_seconds: float = 120.0

    @classmethod
    def from_env(cls) -> AgentOllamaConfig:
        base = (
            os.getenv("YBY_AGENT_OLLAMA_URL", "").strip()
            or os.getenv("YBY_OLLAMA_BASE_URL", "").strip()
            or "http://localhost:11434"
        ).rstrip("/")
        model = (
            os.getenv("YBY_AGENT_MODEL", "").strip()
            or os.getenv("YBY_LOCAL_MODEL", "").strip()
            or DEFAULT_AGENT_MODEL
        )
        temp = float(os.getenv("YBY_AGENT_TEMPERATURE", str(DEFAULT_TEMPERATURE)))
        ctx = int(os.getenv("YBY_AGENT_NUM_CTX", str(DEFAULT_NUM_CTX)))
        timeout = float(os.getenv("YBY_AGENT_TIMEOUT", "120"))
        return cls(
            base_url=base,
            model=model,
            temperature=temp,
            num_ctx=ctx,
            timeout_seconds=timeout,
        )


@dataclass(frozen=True)
class OllamaTurnMetrics:
    duration_ms: float
    prompt_eval_count: int | None
    eval_count: int | None
    model: str


class InstrumentedOllamaProvider(OllamaProvider):
    def __init__(self, config: AgentOllamaConfig) -> None:
        super().__init__(config.base_url, timeout=config.timeout_seconds)
        self._config = config
        self.last_metrics: OllamaTurnMetrics | None = None

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        url = f"{self.base_url}/api/generate"
        payload = build_ollama_generate_payload(prompt, model=model, system=system)
        options = dict(payload.get("options") or {})
        options["temperature"] = self._config.temperature
        options["num_ctx"] = self._config.num_ctx
        payload["options"] = options

        started = time.perf_counter()
        try:
            response = self._session.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ProviderError(f"Ollama indisponível ({exc})") from exc

        if response.status_code >= 400:
            raise ProviderError(f"Ollama HTTP {response.status_code}")

        body = response.json()
        text = body.get("response")
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("resposta vazia do Ollama")

        duration_ms = (time.perf_counter() - started) * 1000
        self.last_metrics = OllamaTurnMetrics(
            duration_ms=duration_ms,
            prompt_eval_count=_as_int(body.get("prompt_eval_count")),
            eval_count=_as_int(body.get("eval_count")),
            model=model,
        )
        return text


class YbyPlanner:
    """Planejador via Ollama (`/api/generate`)."""

    def __init__(self, provider: InstrumentedOllamaProvider, *, model: str | None = None) -> None:
        self._provider = provider
        self._model = model or provider._config.model

    def plan(
        self,
        *,
        question: str,
        tools_blurb: str,
        history: list[dict[str, Any]],
        tools_remaining: int,
        safety_warnings: list[str] | None = None,
    ) -> AgentStep:
        import json

        prompt = build_planner_prompt(
            question=question,
            tools_blurb=tools_blurb,
            tools_remaining=tools_remaining,
            history_json=json.dumps(history, ensure_ascii=False),
            safety_warnings=safety_warnings or [],
        )
        raw = self._provider.complete(prompt, model=self._model, system=SYSTEM_PROMPT)
        return parse_agent_step(raw)


def create_default_planner() -> YbyPlanner:
    config = AgentOllamaConfig.from_env()
    provider = InstrumentedOllamaProvider(config)
    return YbyPlanner(provider)


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None