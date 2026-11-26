"""Schemas Pydantic v2 das pontes de protocolo (BLE GATT e tráfego IoT local) -> MQTT."""

from __future__ import annotations

import re
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TOPIC_BLE_TELEMETRY = "yby/bridges/ble/{mac}/telemetry"
TOPIC_BLE_CMD = "yby/bridges/ble/{mac}/cmd"
TOPIC_TRAFFIC_EVENT = "yby/bridges/traffic/{source}/event"

BLE_BASE_UUID_SUFFIX = "-0000-1000-8000-00805f9b34fb"
UUID_BATTERY_LEVEL = f"00002a19{BLE_BASE_UUID_SUFFIX}"
UUID_DEVICE_NAME = f"00002a00{BLE_BASE_UUID_SUFFIX}"

_HEX_ADDRESS = re.compile(r"^(?:[0-9a-f]{12}|[0-9a-f]{32})$")
_FULL_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_SOURCE_LABEL = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

CharacteristicProperty = Literal[
    "read", "write", "write-without-response", "notify", "indicate"
]
ValueEncoding = Literal["hex", "utf8", "uint8", "uint16le", "uint32le"]


def normalize_mac(address: str) -> str:
    """Normaliza endereço BLE (MAC ou UUID CoreBluetooth) para hex minúsculo sem separadores.

    Recusa qualquer valor que não seja hex puro, impedindo injeção de níveis/curingas MQTT
    (`/`, `+`, `#`) no tópico.
    """

    normalized = re.sub(r"[:\-\s]", "", address).lower()
    if not _HEX_ADDRESS.match(normalized):
        raise ValueError("endereço BLE inválido (esperado MAC de 12 dígitos hex ou UUID)")
    return normalized


def format_address(mac: str) -> str:
    """Formato aceito por transportes BLE: AA:BB:CC:DD:EE:FF (ou UUID no CoreBluetooth)."""

    normalized = normalize_mac(mac).upper()
    if len(normalized) == 12:
        return ":".join(normalized[i : i + 2] for i in range(0, 12, 2))
    return (
        f"{normalized[:8]}-{normalized[8:12]}-{normalized[12:16]}-"
        f"{normalized[16:20]}-{normalized[20:]}"
    )


def normalize_uuid(value: str) -> str:
    """Expande UUIDs GATT de 16/32 bits (`2a19`, `0x2A19`) para 128 bits minúsculos."""

    text = value.strip().lower()
    if text.startswith("0x"):
        text = text[2:]
    if re.fullmatch(r"[0-9a-f]{4}", text):
        return f"0000{text}{BLE_BASE_UUID_SUFFIX}"
    if re.fullmatch(r"[0-9a-f]{8}", text):
        return f"{text}{BLE_BASE_UUID_SUFFIX}"
    if _FULL_UUID.match(text):
        return text
    raise ValueError("UUID GATT inválido")


def normalize_source(label: str) -> str:
    """Valida o rótulo de origem usado como nível de tópico MQTT."""

    text = label.strip().lower()
    if not _SOURCE_LABEL.match(text):
        raise ValueError("source deve casar com [a-z0-9][a-z0-9_-]{0,31}")
    return text


class BleCharacteristicProfile(BaseModel):
    """Característica GATT mapeada (nome legível, propriedades e decodificação)."""

    model_config = ConfigDict(extra="forbid")

    uuid: str
    name: str = Field(default="", max_length=64)
    properties: list[CharacteristicProperty] = Field(default_factory=list)
    encoding: ValueEncoding = "hex"
    handle: int | None = Field(default=None, ge=0)

    @field_validator("uuid")
    @classmethod
    def _normalize_uuid(cls, value: str) -> str:
        return normalize_uuid(value)

    @property
    def readable(self) -> bool:
        return "read" in self.properties

    @property
    def writable(self) -> bool:
        return "write" in self.properties or "write-without-response" in self.properties


class BleDeviceProfile(BaseModel):
    """Perfil persistido de um periférico BLE (arquivo JSON por dispositivo)."""

    model_config = ConfigDict(extra="forbid")

    address: str
    name: str = Field(default="", max_length=64)
    vendor: str = Field(default="", max_length=64)
    characteristics: list[BleCharacteristicProfile] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)

    @field_validator("address")
    @classmethod
    def _normalize_address(cls, value: str) -> str:
        return normalize_mac(value)

    def find(self, key: str) -> BleCharacteristicProfile | None:
        """Busca por UUID (curto ou longo) ou por nome."""

        try:
            wanted = normalize_uuid(key)
        except ValueError:
            wanted = ""
        lowered = key.strip().casefold()
        for item in self.characteristics:
            if item.uuid == wanted or (item.name and item.name.casefold() == lowered):
                return item
        return None


class BleTelemetryEvent(BaseModel):
    """Leitura/notificação GATT publicada em `yby/bridges/ble/<mac>/telemetry`."""

    model_config = ConfigDict(extra="forbid")

    mac: str
    characteristic_uuid: str
    name: str = ""
    event: Literal["read", "notify", "write_ack"] = "read"
    raw_hex: str = ""
    value: int | str | None = None
    battery_pct: int | None = Field(default=None, ge=0, le=100)
    sensitivity: Literal["private"] = "private"
    timestamp: float = Field(default_factory=time.time)


class BleCommandMessage(BaseModel):
    """Comando recebido em `yby/bridges/ble/<mac>/cmd` (somente características do perfil)."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["read", "write"]
    characteristic: str = Field(..., min_length=1, max_length=64)
    value_hex: str | None = Field(default=None, max_length=488)
    response: bool = True

    @model_validator(mode="after")
    def _validate_write(self) -> BleCommandMessage:
        if self.action == "write":
            if not self.value_hex:
                raise ValueError("write exige value_hex")
            if len(self.value_hex) % 2 or not re.fullmatch(r"[0-9a-fA-F]+", self.value_hex):
                raise ValueError("value_hex deve ser hex com número par de dígitos")
        elif self.value_hex is not None:
            raise ValueError("read não aceita value_hex")
        return self

    def value_bytes(self) -> bytes:
        return bytes.fromhex(self.value_hex or "")


class NormalizedTrafficEvent(BaseModel):
    """Evento de telemetria IoT local (HTTP/WS/ADB) já sem segredos e PII."""

    model_config = ConfigDict(extra="forbid")

    source: str
    protocol: Literal["http", "ws", "adb"]
    host: str = Field(default="", max_length=128)
    method: str = Field(default="", max_length=16)
    path: str = Field(default="", max_length=256)
    status_code: int | None = None
    direction: Literal["request", "response", "client", "server", "device"] = "response"
    headers: dict[str, str] = Field(default_factory=dict)
    payload: Any = Field(default_factory=dict)
    text_summary: str = Field(default="", max_length=240)
    redactions: int = Field(default=0, ge=0)
    alerts: list[str] = Field(default_factory=list)
    sensitivity: Literal["private"] = "private"
    timestamp: float = Field(default_factory=time.time)

    @field_validator("source")
    @classmethod
    def _validate_source(cls, value: str) -> str:
        return normalize_source(value)


class TrafficAlertRule(BaseModel):
    """Regra de alerta curto para o T-Watch (texto vem da regra, nunca do payload)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=40)
    message: str | None = Field(default=None, max_length=32)
    host_contains: str | None = None
    path_contains: str | None = None
    json_path: str | None = Field(default=None, description="Caminho com pontos, ex.: door.state")
    equals: Any | None = None
    contains: str | None = None
    gt: float | None = None
    lt: float | None = None
    haptic: bool = False

    @model_validator(mode="after")
    def _require_condition(self) -> TrafficAlertRule:
        conditions = (
            self.host_contains,
            self.path_contains,
            self.json_path,
            self.contains,
        )
        if all(item is None for item in conditions):
            raise ValueError("a regra precisa de ao menos uma condição")
        if self.json_path is None and any(x is not None for x in (self.equals, self.gt, self.lt)):
            raise ValueError("equals/gt/lt exigem json_path")
        return self

    @property
    def alert_text(self) -> str:
        return (self.message or self.name)[:32]
