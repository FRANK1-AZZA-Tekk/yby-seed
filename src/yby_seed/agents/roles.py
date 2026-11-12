"""Agentes especializados (Architect, Builder, Auditor)."""

from __future__ import annotations

import asyncio
import json
from functools import partial
from typing import Any

from openai import OpenAI

from src.yby_seed.agents.state import MissionState
from src.yby_seed.config import Settings, get_settings
from src.yby_seed.memory.retriever import fetch_context
from src.yby_seed.models import StructuredCode

DOMAIN_RAG: dict[str, str | None] = {
    "python_fastapi": "yby_arch",
    "esp_idf": "esp_idf",
    "lvgl_v9": "lvgl",
    "modbus_rtu": "modbus",
}

DOMAIN_LANGUAGE: dict[str, str] = {
    "python_fastapi": "python",
    "esp_idf": "cpp_embedded",
    "lvgl_v9": "cpp_embedded",
    "modbus_rtu": "python",
}

ARCHITECT_SYSTEM = """Você é o ArchitectAgent do YBY SEED.
Consulte o contexto RAG e produza SOMENTE JSON:
{
  "architecture_plan": {
    "steps": [{"id": 1, "action": "...", "deterministic": true}],
    "constraints": ["..."]
  },
  "gpio_manifest": {
    "pins": [{"gpio": 0, "role": "...", "notes": "..."}]
  }
}
Para domínios sem GPIO (Python/Modbus), use gpio_manifest.pins = []."""

BUILDER_SYSTEM = """Você é o BuilderAgent do YBY SEED.
Gere código determinístico seguindo o plano do arquiteto.
Responda SOMENTE JSON:
{
  "language": "python" | "cpp_embedded",
  "filename": "arquivo.ext",
  "code": "conteúdo integral",
  "tests": "pytest opcional"
}"""

AUDITOR_SYSTEM = """Você é o AuditorAgent do YBY SEED.
Analise stderr do sandbox, identifique causa raiz e proponha correção CIRÚRGICA.
Responda SOMENTE JSON:
{
  "root_cause": "...",
  "fix_guidance": "instruções objetivas para o Builder corrigir sem reescrever tudo"
}"""


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class ArchitectAgent:
    def __init__(self, client: OpenAI, settings: Settings | None = None) -> None:
        self.client = client
        self.settings = settings or get_settings()

    def _model_for_context(self, prompt: str, rag: str) -> str:
        tokens = _approx_tokens(prompt) + _approx_tokens(rag)
        if tokens > 1500:
            return "yby-cloud-coder"
        return self.settings.litellm_model

    async def run(self, state: MissionState) -> MissionState:
        rag_domain = DOMAIN_RAG.get(state.domain, "yby_arch")
        state.rag_context = await fetch_context(state.user_intent, rag_domain, top_k=6)

        user_content = (
            f"Domínio: {state.domain}\n"
            f"Intenção:\n{state.user_intent}\n\n"
            f"Contexto RAG:\n{state.rag_context or '(vazio)'}"
        )
        model = self._model_for_context(state.user_intent, state.rag_context)
        payload = await asyncio.get_running_loop().run_in_executor(
            None,
            partial(self._complete_json, ARCHITECT_SYSTEM, user_content, model),
        )
        state.architecture_plan = payload.get("architecture_plan")
        state.gpio_manifest = payload.get("gpio_manifest")
        return state

    def _complete_json(self, system: str, user: str, model: str) -> dict[str, Any]:
        completion = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content or "{}"
        return json.loads(raw)


class BuilderAgent:
    def __init__(self, client: OpenAI, settings: Settings | None = None) -> None:
        self.client = client
        self.settings = settings or get_settings()

    async def run(self, state: MissionState) -> MissionState:
        language = DOMAIN_LANGUAGE.get(state.domain, "python")
        plan_json = json.dumps(state.architecture_plan or {}, ensure_ascii=False)
        gpio_json = json.dumps(state.gpio_manifest or {}, ensure_ascii=False)
        user_content = (
            f"Domínio: {state.domain}\n"
            f"language esperado: {language}\n"
            f"Plano:\n{plan_json}\n"
            f"GPIO:\n{gpio_json}\n"
            f"Intenção:\n{state.user_intent}\n"
        )
        if state.auditor_guidance:
            user_content += f"\nCorreção do Auditor:\n{state.auditor_guidance}\n"

        payload = await asyncio.get_running_loop().run_in_executor(
            None,
            partial(
                self._complete_json,
                BUILDER_SYSTEM,
                user_content,
                self.settings.litellm_model,
            ),
        )
        payload.setdefault("language", language)
        state.generated_code = StructuredCode.model_validate(payload)
        return state

    def _complete_json(self, system: str, user: str, model: str) -> dict[str, Any]:
        completion = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content or "{}"
        return json.loads(raw)


class AuditorAgent:
    def __init__(self, client: OpenAI, settings: Settings | None = None) -> None:
        self.client = client
        self.settings = settings or get_settings()

    async def run(self, state: MissionState) -> MissionState:
        code_preview = (state.generated_code.code if state.generated_code else "")[:4000]
        user_content = (
            f"Domínio: {state.domain}\n"
            f"stdout:\n{state.last_stdout}\n"
            f"stderr:\n{state.last_stderr}\n"
            f"Trecho do código:\n{code_preview}\n"
        )
        payload = await asyncio.get_running_loop().run_in_executor(
            None,
            partial(
                self._complete_json,
                AUDITOR_SYSTEM,
                user_content,
                self.settings.litellm_model,
            ),
        )
        root = payload.get("root_cause", "")
        fix = payload.get("fix_guidance", "")
        state.auditor_guidance = f"Causa: {root}\nGuia: {fix}"
        state.validation_logs.append(state.auditor_guidance)
        return state

    def _complete_json(self, system: str, user: str, model: str) -> dict[str, Any]:
        completion = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content or "{}"
        return json.loads(raw)
