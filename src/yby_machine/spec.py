"""Modelo Pydantic v2 da especificação de micro-app (Spec-First)."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_PHONE_E164 = re.compile(r"^\+?[0-9]{10,15}$")
# EMV QR estático BR Code começa tipicamente com 000201
_PIX_BR_PREFIX = "000201"


class BrFieldType(str, Enum):
    """Tipos de campo com foco em dados brasileiros do MVP."""

    texto = "texto"
    numero = "numero"
    data = "data"
    cpf = "cpf"
    cnpj = "cnpj"
    cep = "cep"
    moeda_brl = "moeda_brl"
    telefone_br = "telefone_br"


class PaymentStatus(str, Enum):
    """Status de pagamento exibidos no app gerado."""

    pago = "Pago"
    pendente_fiado = "Pendente/Fiado"
    sinal_50 = "Sinal 50%"


class FieldSpec(BaseModel):
    """Um campo de entidade."""

    name: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    type: BrFieldType = BrFieldType.texto
    required: bool = True

    @field_validator("name")
    @classmethod
    def _name_ident(cls, value: str) -> str:
        cleaned = value.strip()
        if not _IDENT.match(cleaned):
            raise ValueError("name deve ser identificador (letras, dígitos, _)")
        return cleaned

    @field_validator("label")
    @classmethod
    def _label_strip(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("label vazio")
        return cleaned


class EntitySpec(BaseModel):
    """Entidade persistida no localStorage do PWA (IndexedDB fica para depois)."""

    name: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    fields: list[FieldSpec] = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def _name_ident(cls, value: str) -> str:
        cleaned = value.strip()
        if not _IDENT.match(cleaned):
            raise ValueError("name deve ser identificador (letras, dígitos, _)")
        return cleaned

    @field_validator("label")
    @classmethod
    def _label_strip(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("label vazio")
        return cleaned


class ActionSpec(BaseModel):
    """Ação de negócio (botão / fluxo) no app."""

    name: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=400)

    @field_validator("name")
    @classmethod
    def _name_ident(cls, value: str) -> str:
        cleaned = value.strip()
        if not _IDENT.match(cleaned):
            raise ValueError("name deve ser identificador (letras, dígitos, _)")
        return cleaned


class CalcRule(BaseModel):
    """Regra de cálculo simples (ex.: total = qtd * preço)."""

    name: str = Field(min_length=1, max_length=80)
    expression: str = Field(min_length=1, max_length=200)
    result_field: str = Field(min_length=1, max_length=80)

    @field_validator("name", "result_field")
    @classmethod
    def _ident_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not _IDENT.match(cleaned):
            raise ValueError("deve ser identificador (letras, dígitos, _)")
        return cleaned


class PixConfig(BaseModel):
    """Payload Pix estático (BR Code string). MVP: sem EMV/CRC completo."""

    enabled: bool = False
    payload: str = Field(default="", max_length=512)
    label: str = Field(default="Copiar Pix", max_length=80)

    @model_validator(mode="after")
    def _pix_payload_when_enabled(self) -> PixConfig:
        if not self.enabled:
            return self
        payload = (self.payload or "").strip()
        if not payload:
            raise ValueError("pix.enabled exige payload BR Code não vazio")
        if not payload.startswith(_PIX_BR_PREFIX):
            raise ValueError("pix.payload deve parecer BR Code (prefixo 000201)")
        self.payload = payload
        return self


class WhatsAppConfig(BaseModel):
    """Botão wa.me com resumo do registro."""

    enabled: bool = True
    phone_e164: str = Field(default="", max_length=20)
    summary_prefix: str = Field(default="Resumo YBY", max_length=120)

    @field_validator("phone_e164")
    @classmethod
    def _phone_optional_e164(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        if not _PHONE_E164.match(cleaned):
            raise ValueError("phone_e164 deve ter 10–15 dígitos (opcional +)")
        return cleaned


class YBYSpec(BaseModel):
    """Especificação completa de um micro-app gerado pela Machine."""

    name: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=400)
    entities: list[EntitySpec] = Field(min_length=1)
    actions: list[ActionSpec] = Field(default_factory=list)
    calc_rules: list[CalcRule] = Field(default_factory=list)
    payment_statuses: list[PaymentStatus] = Field(
        default_factory=lambda: list(PaymentStatus),
    )
    pix: PixConfig = Field(default_factory=PixConfig)
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    theme: Literal["yby"] = "yby"
    version: Literal["1"] = "1"

    @field_validator("name")
    @classmethod
    def _name_ident(cls, value: str) -> str:
        cleaned = value.strip()
        if not _IDENT.match(cleaned):
            raise ValueError("name deve ser identificador (letras, dígitos, _)")
        return cleaned

    @field_validator("title")
    @classmethod
    def _title_strip(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title vazio")
        return cleaned


def yby_spec_json_schema() -> dict[str, Any]:
    """JSON Schema de `YBYSpec` (Pydantic `model_json_schema`) para prompt/docs/API."""

    return YBYSpec.model_json_schema()


def yby_spec_schema_for_prompt() -> str:
    """Schema compacto (JSON) para o system prompt do tradutor."""

    import json

    return json.dumps(yby_spec_json_schema(), ensure_ascii=False, separators=(",", ":"))
