"""Ponte BLE GATT -> MQTT (telemetria e comandos) com transporte injetável.

`bleak` é importado de forma preguiçosa por `BleakTransport`; os testes usam um
`BleTransport` em memória. Escritas GATT só são aceitas em características marcadas
como graváveis no perfil salvo do dispositivo (allowlist por dispositivo).
"""

from __future__ import annotations

import asyncio
import importlib
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.security.cloud_sanitizer import sanitize_for_cloud
from src.yby.audio.mqtt_bus import MqttPublisher
from src.yby.bridges.schemas import (
    TOPIC_BLE_CMD,
    TOPIC_BLE_TELEMETRY,
    UUID_BATTERY_LEVEL,
    UUID_DEVICE_NAME,
    BleCharacteristicProfile,
    BleCommandMessage,
    BleDeviceProfile,
    BleTelemetryEvent,
    ValueEncoding,
    format_address,
    normalize_mac,
    normalize_uuid,
)

MAX_WRITE_BYTES = 244
_CMD_TOPIC_PATTERN = re.compile(r"^yby/bridges/ble/([0-9a-f]{12}|[0-9a-f]{32})/cmd$")

STANDARD_CHARACTERISTICS: dict[str, tuple[str, ValueEncoding]] = {
    UUID_DEVICE_NAME: ("device_name", "utf8"),
    UUID_BATTERY_LEVEL: ("battery_level", "uint8"),
    normalize_uuid("2a24"): ("model_number", "utf8"),
    normalize_uuid("2a26"): ("firmware_revision", "utf8"),
    normalize_uuid("2a27"): ("hardware_revision", "utf8"),
    normalize_uuid("2a28"): ("software_revision", "utf8"),
    normalize_uuid("2a29"): ("manufacturer_name", "utf8"),
}


class BleBridgeError(RuntimeError):
    """Erro controlado da ponte BLE (perfil ausente, escrita não permitida, etc.)."""


class BleDiscoveredDevice(BaseModel):
    """Periférico visto em `scan()`; `characteristics` vem do transporte, se disponível."""

    model_config = ConfigDict(extra="forbid")

    address: str
    name: str = ""
    rssi: int | None = None
    service_uuids: list[str] = Field(default_factory=list)
    characteristics: list[BleCharacteristicProfile] = Field(default_factory=list)


@runtime_checkable
class BleTransport(Protocol):
    async def scan(self, timeout: float = 5.0) -> list[BleDiscoveredDevice]: ...

    async def read_gatt(self, address: str, char_uuid: str) -> bytes: ...

    async def write_gatt(
        self,
        address: str,
        char_uuid: str,
        data: bytes,
        *,
        response: bool = True,
    ) -> None: ...


class BleakTransport:
    """Transporte real sobre `bleak` (import preguiçoso; `bleak_module` permite mocks)."""

    def __init__(self, *, bleak_module: Any = None, connect_timeout: float = 15.0) -> None:
        self._bleak = bleak_module
        self._connect_timeout = connect_timeout

    def _module(self) -> Any:
        if self._bleak is None:
            self._bleak = importlib.import_module("bleak")
        return self._bleak

    async def scan(self, timeout: float = 5.0) -> list[BleDiscoveredDevice]:
        bleak = self._module()
        found = await bleak.BleakScanner.discover(timeout=timeout, return_adv=True)
        devices: list[BleDiscoveredDevice] = []
        for device, adv in found.values():
            devices.append(
                BleDiscoveredDevice(
                    address=str(device.address),
                    name=str(getattr(adv, "local_name", None) or device.name or ""),
                    rssi=getattr(adv, "rssi", None),
                    service_uuids=[str(u).lower() for u in getattr(adv, "service_uuids", [])],
                )
            )
        return devices

    async def list_characteristics(self, address: str) -> list[BleCharacteristicProfile]:
        bleak = self._module()
        async with bleak.BleakClient(address, timeout=self._connect_timeout) as client:
            return [
                BleCharacteristicProfile(
                    uuid=str(char.uuid),
                    properties=[p for p in char.properties if p in _KNOWN_PROPERTIES],
                    handle=getattr(char, "handle", None),
                )
                for service in client.services
                for char in service.characteristics
            ]

    async def read_gatt(self, address: str, char_uuid: str) -> bytes:
        bleak = self._module()
        async with bleak.BleakClient(address, timeout=self._connect_timeout) as client:
            return bytes(await client.read_gatt_char(char_uuid))

    async def write_gatt(
        self,
        address: str,
        char_uuid: str,
        data: bytes,
        *,
        response: bool = True,
    ) -> None:
        bleak = self._module()
        async with bleak.BleakClient(address, timeout=self._connect_timeout) as client:
            await client.write_gatt_char(char_uuid, data, response=response)


_KNOWN_PROPERTIES = frozenset({"read", "write", "write-without-response", "notify", "indicate"})


def decode_value(data: bytes, encoding: ValueEncoding) -> int | str | None:
    """Decodifica bytes GATT; textos passam por `sanitize_for_cloud` (nomes podem ser PII)."""

    if not data:
        return None
    if encoding == "uint8":
        return data[0]
    if encoding == "uint16le" and len(data) >= 2:
        return int.from_bytes(data[:2], "little")
    if encoding == "uint32le" and len(data) >= 4:
        return int.from_bytes(data[:4], "little")
    if encoding == "utf8":
        text = data.decode("utf-8", errors="replace").replace("\x00", "").strip()
        return sanitize_for_cloud(text, environ={"YBY_CLOUD_SANITIZE": "1"}).text[:128]
    return data.hex()


class BleGattBridge:
    """Mapeia GATT -> MQTT: perfis JSON, telemetria QoS 1 e comandos controlados."""

    def __init__(
        self,
        publisher: MqttPublisher,
        *,
        transport: BleTransport | None = None,
        profiles_dir: str | Path | None = None,
        vendor_characteristics: dict[str, tuple[str, ValueEncoding]] | None = None,
    ) -> None:
        self._publisher = publisher
        self._transport: BleTransport = transport or BleakTransport()
        self.profiles_dir = Path(profiles_dir) if profiles_dir else None
        self._known: dict[str, tuple[str, ValueEncoding]] = dict(STANDARD_CHARACTERISTICS)
        for uuid, mapping in (vendor_characteristics or {}).items():
            self.register_characteristic(uuid, *mapping)
        self._scanned: dict[str, BleDiscoveredDevice] = {}
        self._profiles: dict[str, BleDeviceProfile] = {}

    def register_characteristic(
        self,
        uuid: str,
        name: str,
        encoding: ValueEncoding = "hex",
    ) -> None:
        """Registra UUID vendor (ex.: Baseus Bowie MC2 Air) descoberto em engenharia local."""

        self._known[normalize_uuid(uuid)] = (name, encoding)

    def name_characteristic(self, profile: BleCharacteristicProfile) -> BleCharacteristicProfile:
        known = self._known.get(profile.uuid)
        if known is not None and not profile.name:
            return profile.model_copy(update={"name": known[0], "encoding": known[1]})
        if not profile.name:
            return profile.model_copy(update={"name": f"vendor_{profile.uuid[:8]}"})
        return profile

    async def scan(self, timeout: float = 5.0) -> list[BleDiscoveredDevice]:
        devices = await self._transport.scan(timeout)
        self._scanned = {normalize_mac(d.address): d for d in devices}
        return devices

    async def build_profile(self, address: str, *, vendor: str = "") -> BleDeviceProfile:
        """Cria perfil a partir do último scan (e características do transporte, se houver)."""

        mac = normalize_mac(address)
        device = self._scanned.get(mac)
        characteristics = list(device.characteristics) if device else []
        lister = getattr(self._transport, "list_characteristics", None)
        if not characteristics and callable(lister):
            characteristics = list(await lister(format_address(mac)))
        if not characteristics:
            raise BleBridgeError("nenhuma característica GATT descoberta para o dispositivo")
        profile = BleDeviceProfile(
            address=mac,
            name=(device.name if device else "")[:64],
            vendor=vendor,
            characteristics=[self.name_characteristic(item) for item in characteristics],
        )
        self._profiles[mac] = profile
        return profile

    def save_profile(self, profile: BleDeviceProfile, directory: str | Path | None = None) -> Path:
        base = Path(directory) if directory else self.profiles_dir
        if base is None:
            raise BleBridgeError("profiles_dir não configurado")
        base.mkdir(parents=True, exist_ok=True)
        path = base / f"{profile.address}.json"
        path.write_text(profile.model_dump_json(indent=2) + "\n", encoding="utf-8")
        self._profiles[profile.address] = profile
        return path

    def load_profile(
        self,
        address_or_path: str | Path,
        directory: str | Path | None = None,
    ) -> BleDeviceProfile:
        candidate = Path(address_or_path)
        if candidate.suffix == ".json" and candidate.is_file():
            path = candidate
        else:
            base = Path(directory) if directory else self.profiles_dir
            if base is None:
                raise BleBridgeError("profiles_dir não configurado")
            path = base / f"{normalize_mac(str(address_or_path))}.json"
        if not path.is_file():
            raise BleBridgeError("perfil BLE não encontrado")
        try:
            profile = BleDeviceProfile.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValidationError, ValueError) as exc:
            raise BleBridgeError("perfil BLE inválido") from exc
        self._profiles[profile.address] = profile
        return profile

    def list_profiles(self) -> list[BleDeviceProfile]:
        """Perfis em memória mais os salvos em `profiles_dir` (arquivos inválidos ignorados)."""

        if self.profiles_dir is not None and self.profiles_dir.is_dir():
            for path in sorted(self.profiles_dir.glob("*.json")):
                try:
                    self.load_profile(path)
                except BleBridgeError:
                    continue
        return sorted(self._profiles.values(), key=lambda item: item.address)

    def _profile_for(self, mac: str) -> BleDeviceProfile:
        profile = self._profiles.get(mac)
        if profile is None and self.profiles_dir is not None:
            try:
                profile = self.load_profile(mac)
            except BleBridgeError:
                profile = None
        if profile is None:
            raise BleBridgeError("dispositivo sem perfil salvo")
        return profile

    async def _publish(self, event: BleTelemetryEvent) -> None:
        await self._publisher.publish(
            TOPIC_BLE_TELEMETRY.format(mac=event.mac),
            event.model_dump_json(),
            qos=1,
            retain=False,
        )

    async def read_and_publish(
        self,
        address: str,
        characteristic: str,
        *,
        event_kind: str = "read",
    ) -> BleTelemetryEvent:
        mac = normalize_mac(address)
        profile = self._profile_for(mac)
        char = profile.find(characteristic)
        if char is None:
            raise BleBridgeError("característica fora do perfil")
        if not char.readable:
            raise BleBridgeError("característica não é legível")
        data = await self._transport.read_gatt(format_address(mac), char.uuid)
        value = decode_value(data, char.encoding)
        battery = (
            value
            if char.uuid == UUID_BATTERY_LEVEL and isinstance(value, int) and 0 <= value <= 100
            else None
        )
        event = BleTelemetryEvent(
            mac=mac,
            characteristic_uuid=char.uuid,
            name=char.name,
            event=event_kind,  # type: ignore[arg-type]
            raw_hex=data.hex(),
            value=value,
            battery_pct=battery,
        )
        await self._publish(event)
        return event

    async def poll_once(self, address: str) -> list[BleTelemetryEvent]:
        """Lê e publica todas as características legíveis do perfil."""

        profile = self._profile_for(normalize_mac(address))
        events: list[BleTelemetryEvent] = []
        for char in profile.characteristics:
            if char.readable:
                events.append(await self.read_and_publish(address, char.uuid))
        return events

    async def write_and_ack(
        self,
        address: str,
        characteristic: str,
        data: bytes,
        *,
        response: bool = True,
    ) -> BleTelemetryEvent:
        mac = normalize_mac(address)
        char = self._profile_for(mac).find(characteristic)
        if char is None:
            raise BleBridgeError("característica fora do perfil")
        if not char.writable:
            raise BleBridgeError("característica não é gravável no perfil")
        if not data or len(data) > MAX_WRITE_BYTES:
            raise BleBridgeError(f"escrita deve ter 1..{MAX_WRITE_BYTES} bytes")
        await self._transport.write_gatt(
            format_address(mac), char.uuid, data, response=response
        )
        event = BleTelemetryEvent(
            mac=mac,
            characteristic_uuid=char.uuid,
            name=char.name,
            event="write_ack",
            raw_hex=data.hex(),
        )
        await self._publish(event)
        return event

    async def handle_command(
        self,
        address: str,
        payload: str | bytes,
    ) -> BleTelemetryEvent:
        """Processa o JSON de `yby/bridges/ble/<mac>/cmd` (read/write permitido pelo perfil)."""

        try:
            message = BleCommandMessage.model_validate_json(payload)
        except ValidationError as exc:
            raise BleBridgeError(f"comando BLE inválido: {len(exc.errors())} erro(s)") from exc
        if message.action == "read":
            return await self.read_and_publish(address, message.characteristic)
        return await self.write_and_ack(
            address,
            message.characteristic,
            message.value_bytes(),
            response=message.response,
        )

    async def handle_mqtt_message(
        self,
        topic: str,
        payload: str | bytes,
    ) -> BleTelemetryEvent | None:
        """Callback para o assinante MQTT: valida o tópico `/cmd` e despacha o comando."""

        match = _CMD_TOPIC_PATTERN.match(topic)
        if match is None:
            return None
        try:
            return await self.handle_command(match.group(1), payload)
        except (BleBridgeError, ValueError) as exc:
            await self._publisher.publish(
                TOPIC_BLE_TELEMETRY.format(mac=match.group(1)),
                json.dumps({"error": str(exc)[:160], "sensitivity": "private"}),
                qos=1,
                retain=False,
            )
            return None

    @staticmethod
    def cmd_topic(address: str) -> str:
        return TOPIC_BLE_CMD.format(mac=normalize_mac(address))

    async def run_poll_loop(
        self,
        addresses: Sequence[str],
        *,
        interval: float = 60.0,
        iterations: int | None = None,
    ) -> None:
        """Laço de polling simples; `iterations` limita execuções (útil em testes)."""

        count = 0
        while iterations is None or count < iterations:
            for address in addresses:
                try:
                    await self.poll_once(address)
                except (BleBridgeError, OSError, TimeoutError):
                    continue
            count += 1
            if iterations is None or count < iterations:
                await asyncio.sleep(interval)
