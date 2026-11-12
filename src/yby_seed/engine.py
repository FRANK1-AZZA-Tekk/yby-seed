"""Loop determinístico de Vibe Coding (LiteLLM → sandbox → MQTT → dataset)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import paho.mqtt.client as mqtt
from openai import OpenAI

from src.yby_seed.config import Settings, get_settings
from src.yby_seed.memory.retriever import fetch_context
from src.yby_seed.models import (
    DomainKind,
    GenerateRequest,
    GenerateResponse,
    StructuredCode,
)
from src.yby_seed.sandbox import execute_validated

STRUCTURE_SYSTEM = """Você gera código determinístico para YBY SEED.
Responda SOMENTE com JSON válido no formato:
{
  "language": "python" | "cpp_embedded",
  "filename": "nome_do_arquivo",
  "code": "conteúdo completo",
  "tests": "pytest opcional (apenas python)"
}
Sem markdown fora do campo code."""


DOMAIN_MAP: dict[DomainKind, tuple[str, str | None]] = {
    "python_fastapi": ("python", "yby_arch"),
    "esp_idf": ("cpp_embedded", "esp_idf"),
    "lvgl_v9": ("cpp_embedded", "lvgl"),
    "modbus_rtu": ("python", "modbus"),
}


class SeedEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = OpenAI(
            base_url=self.settings.litellm_base_url,
            api_key=self.settings.litellm_api_key,
        )

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        return await generate_and_verify(request, settings=self.settings, client=self._client)


async def generate_and_verify(
    request: GenerateRequest,
    *,
    settings: Settings | None = None,
    client: OpenAI | None = None,
) -> GenerateResponse:
    settings = settings or get_settings()
    client = client or OpenAI(
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
    )

    domain = request.domain or "python_fastapi"
    language, rag_domain = DOMAIN_MAP.get(domain, ("python", "yby_arch"))
    rag_ctx = await fetch_context(request.prompt, rag_domain, top_k=4)

    system_prompt = request.system_prompt or STRUCTURE_SYSTEM
    user_prompt = request.prompt
    if rag_ctx:
        user_prompt = f"Contexto técnico:\n{rag_ctx}\n\nPedido:\n{request.prompt}"

    last_stdout = ""
    last_stderr = ""
    artifact: StructuredCode | None = None

    for attempt in range(1, settings.max_generation_attempts + 1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if last_stderr and attempt > 1:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "A validação falhou. Corrija o código.\n"
                        f"stderr:\n{last_stderr}\nstdout:\n{last_stdout}"
                    ),
                }
            )

        try:
            completion = client.chat.completions.create(
                model=settings.litellm_model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content or "{}"
            payload = json.loads(raw)
            payload.setdefault("language", language)
            artifact = StructuredCode.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            last_stderr = str(exc)
            continue

        ok, last_stdout, last_stderr = execute_validated(
            language=artifact.language,
            code=artifact.code,
            filename=artifact.filename,
            tests=artifact.tests,
            settings=settings,
        )
        if ok:
            dataset_saved = _append_dataset(
                settings.datasets_path,
                system_prompt,
                request.prompt,
                artifact.code,
            )
            mqtt_published = _publish_mqtt(settings, request, artifact)
            return GenerateResponse(
                success=True,
                attempts=attempt,
                code=artifact.code,
                filename=artifact.filename,
                language=artifact.language,
                stdout=last_stdout,
                stderr=last_stderr,
                dataset_saved=dataset_saved,
                mqtt_published=mqtt_published,
            )

    return GenerateResponse(
        success=False,
        attempts=settings.max_generation_attempts,
        code=artifact.code if artifact else None,
        filename=artifact.filename if artifact else None,
        language=artifact.language if artifact else language,
        stdout=last_stdout,
        stderr=last_stderr,
    )


def _append_dataset(path: Path, system: str, user: str, assistant: str) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ]
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def _publish_mqtt(settings: Settings, request: GenerateRequest, artifact: StructuredCode) -> bool:
    payload = json.dumps(
        {
            "prompt": request.prompt,
            "domain": request.domain,
            "filename": artifact.filename,
            "language": artifact.language,
            "validated_at": datetime.now(UTC).isoformat(),
        },
        ensure_ascii=False,
    )
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=30)
        client.publish(settings.mqtt_topic_validated, payload, qos=1)
        client.disconnect()
        return True
    except Exception:  # noqa: BLE001
        return False
