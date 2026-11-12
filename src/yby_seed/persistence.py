"""Persistência pós-validação (dataset ChatML + MQTT)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import paho.mqtt.client as mqtt

from src.yby_seed.config import Settings
from src.yby_seed.models import GenerateRequest, StructuredCode


def append_dataset(path: Path, system: str, user: str, assistant: str) -> bool:
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


def publish_validated_code(
    settings: Settings,
    request: GenerateRequest,
    artifact: StructuredCode,
) -> bool:
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
