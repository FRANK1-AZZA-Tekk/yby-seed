"""Modelo Pydantic v2 da especificação de micro-app (Spec-First)."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


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


class EntitySpec(BaseModel):
    """Entidade persistida no IndexedDB/localStorage do PWA."""

    name: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    fields: list[FieldSpec] = Field(min_length=1)


class ActionSpec(BaseModel):
    """Ação de negócio (botão / fluxo) no app."""

    name: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=400)


class CalcRule(BaseModel):
    """Regra de cálculo simples (ex.: total = qtd * preço)."""

    name: str = Field(min_length=1, max_length=80)
    expression: str = Field(min_length=1, max_length=200)
    result_field: str = Field(min_length=1, max_length=80)


class PixConfig(BaseModel):
    """Payload Pix estático (BR Code string). MVP: sem EMV/CRC completo."""

    enabled: bool = False
    payload: str = Field(default="", max_length=512)
    label: str = Field(default="Pagar com Pix", max_length=80)


class WhatsAppConfig(BaseModel):
    """Botão wa.me com resumo do registro."""

    enabled: bool = True
    phone_e164: str = Field(default="", max_length=20)
    summary_prefix: str = Field(default="Resumo YBY", max_length=120)


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
