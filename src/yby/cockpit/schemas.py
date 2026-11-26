"""Schemas Pydantic v2 da ponte PhoneBox (Moto Edge 30) para o Cockpit YBY."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DEFAULT_COCKPIT_MQTT_TOPIC = "yby/cockpit/action"
_SAFE_TOPIC_RE = re.compile(r"^yby/cockpit/[a-zA-Z0-9_/-]+$")
_SAFE_TAG_RE = re.compile(r"^[A-Za-z0-9À-ÿ/_-]+$")

CockpitAction = Literal["capture_inbox", "trigger_reindex", "publish_mqtt"]


class ServiceHealth(BaseModel):
    """Estado compacto de um serviço local para widgets do PhoneBox."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["up", "down", "unconfigured"]
    latency_ms: float | None = None
    detail: str = ""


class CockpitServicesStatus(BaseModel):
    """Estado consolidado dos serviços locais do PC Hub."""

    model_config = ConfigDict(extra="forbid")

    fastapi: ServiceHealth
    redis: ServiceHealth
    postgres_pgvector: ServiceHealth
    mqtt: ServiceHealth


class CockpitStatusResponse(BaseModel):
    """Payload compacto de baixa latência retornado em `GET /api/v1/cockpit/status`."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded"]
    timestamp: str
    services: CockpitServicesStatus
    yby_machine_specs_count: int = Field(ge=0)
    active_tasks: int = Field(ge=0)
    pending_edge_events: int = Field(default=0, ge=0)
    indexed_chunks: int = Field(default=0, ge=0)


class CockpitWebhookRequest(BaseModel):
    """Comando tátil enviado pelos botões/regras reativas do PhoneBox."""

    model_config = ConfigDict(extra="forbid")

    action: CockpitAction
    source: str = Field(default="phonebox-edge30", min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=8000)
    title: str | None = Field(default=None, max_length=160)
    tags: list[str] = Field(default_factory=list, max_length=16)
    force_reindex: bool = False
    mqtt_topic: str = Field(
        default=DEFAULT_COCKPIT_MQTT_TOPIC,
        min_length=1,
        max_length=128,
    )
    mqtt_payload: dict[str, Any] | None = None

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in values:
            tag = raw.strip().lstrip("#")
            if not tag:
                continue
            if not _SAFE_TAG_RE.match(tag):
                raise ValueError(f"tag inválida: {raw!r}")
            cleaned.append(tag)
        return cleaned

    @field_validator("mqtt_topic")
    @classmethod
    def _validate_mqtt_topic(cls, value: str) -> str:
        topic = value.strip()
        if not _SAFE_TOPIC_RE.match(topic) or ".." in topic:
            raise ValueError("mqtt_topic deve estar sob o prefixo seguro 'yby/cockpit/'")
        return topic

    @model_validator(mode="after")
    def _validate_action_payload(self) -> CockpitWebhookRequest:
        if self.action == "capture_inbox":
            if self.note is None or not self.note.strip():
                raise ValueError("action='capture_inbox' exige o campo 'note' não vazio")
            self.note = self.note.strip()
            if self.title is not None:
                self.title = self.title.strip() or None
        elif self.action == "publish_mqtt":
            if not isinstance(self.mqtt_payload, dict) or not self.mqtt_payload:
                raise ValueError(
                    "action='publish_mqtt' exige 'mqtt_payload' como objeto JSON não vazio"
                )
        return self


class CockpitWebhookResponse(BaseModel):
    """Resposta estruturada do endpoint `POST /api/v1/cockpit/webhook`."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    action: CockpitAction
    detail: str
    data: dict[str, Any] = Field(default_factory=dict)
