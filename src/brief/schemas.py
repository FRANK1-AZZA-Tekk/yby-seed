"""Contrato YBY-BRIEF (v1). Não autoriza execução."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


BRIEF_SCHEMA = "yby-brief/v1"

# Ordem da entrevista (blocos curtos em PT-BR).
BRIEF_FIELDS: tuple[tuple[str, str], ...] = (
    ("objective", "Qual é o objetivo concreto do software?"),
    ("audience", "Para quem é (público / pessoa usuária)?"),
    ("scope", "O que entra no escopo desta versão?"),
    ("out_of_scope", "O que fica explicitamente fora do escopo?"),
    ("constraints", "Quais restrições (só local, sem nuvem, stack, prazo)?"),
    ("required_data", "Que dados são necessários? Evite senhas e PII."),
    ("acceptance", "Como saberemos que deu certo (critérios de aceite)?"),
    ("risks", "Quais riscos principais você já enxerga?"),
)

_FIELD_KEYS = frozenset(key for key, _ in BRIEF_FIELDS)


class YbyBrief(BaseModel):
    """Brief de produto. Completo ≠ autorização para rodar comandos ou gerar código."""

    schema_version: Literal["yby-brief/v1"] = BRIEF_SCHEMA
    id: str = Field(min_length=1, max_length=64)
    idea: str = Field(min_length=1, max_length=2000)
    objective: str | None = None
    audience: str | None = None
    scope: str | None = None
    out_of_scope: str | None = None
    constraints: str | None = None
    required_data: str | None = None
    acceptance: str | None = None
    risks: str | None = None
    sensitive_kinds: list[str] = Field(default_factory=list)
    status: Literal["draft", "ready", "proposed"] = "draft"
    proposal: str | None = None
    created_at: str = Field(default_factory=lambda: _now())
    updated_at: str = Field(default_factory=lambda: _now())

    def filled(self, key: str) -> bool:
        if key not in _FIELD_KEYS:
            raise KeyError(key)
        value = getattr(self, key)
        return isinstance(value, str) and bool(value.strip())

    def touch(self) -> None:
        self.updated_at = _now()

    def cloud_safe_dict(self) -> dict[str, object]:
        """Payload para exibição/nuvem: campos sensíveis omitidos e texto redigido."""

        from src.engine.secret_gate import redact_for_cloud

        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "id": self.id,
            "status": self.status,
            "sensitive_kinds": list(self.sensitive_kinds),
        }
        for key, _ in BRIEF_FIELDS:
            raw = getattr(self, key)
            if raw is None:
                payload[key] = None
                continue
            if key in {"required_data", "constraints"} and self.sensitive_kinds:
                payload[key] = "[SENSITIVE_OMITTED]"
            else:
                payload[key] = redact_for_cloud(str(raw))
        payload["idea"] = redact_for_cloud(self.idea)
        if self.proposal:
            payload["proposal"] = redact_for_cloud(self.proposal)
        return payload


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
