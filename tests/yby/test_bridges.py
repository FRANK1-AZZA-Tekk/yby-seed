"""Testes 100% offline das pontes BLE GATT e tráfego IoT/ADB -> MQTT."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.yby.audio import TOPIC_TWATCH_CMD, InMemoryMqttBus, TWatchCommand
from src.yby.bridges import (
    AdbEventBridge,
    BleakTransport,
    BleBridgeError,
    BleCharacteristicProfile,
    BleCommandMessage,
    BleDeviceProfile,
    BleDiscoveredDevice,
    BleGattBridge,
    BleTelemetryEvent,
    NormalizedTrafficEvent,
    TrafficAlertRule,
    TrafficBridgeError,
    YbyTrafficAddon,
    scrub_headers_and_payload,
)
from src.yby.bridges.schemas import (
    UUID_BATTERY_LEVEL,
    UUID_DEVICE_NAME,
    format_address,
    normalize_mac,
    normalize_uuid,
)
from src.yby.bridges.traffic_bridge import is_local_host

BASEUS_MAC = "AA:BB:CC:DD:EE:FF"
BASEUS_MAC_NORM = "aabbccddeeff"
VENDOR_UUID = "0000fee1-0000-1000-8000-00805f9b34fb"
TELEMETRY_TOPIC = f"yby/bridges/ble/{BASEUS_MAC_NORM}/telemetry"
CMD_TOPIC = f"yby/bridges/ble/{BASEUS_MAC_NORM}/cmd"


def baseus_device() -> BleDiscoveredDevice:
    return BleDiscoveredDevice(
        address=BASEUS_MAC,
        name="Baseus Bowie MC2 Air",
        rssi=-52,
        characteristics=[
            BleCharacteristicProfile(uuid="2a19", properties=["read", "notify"]),
            BleCharacteristicProfile(uuid="2a00", properties=["read"]),
            BleCharacteristicProfile(uuid=VENDOR_UUID, properties=["read", "write"]),
        ],
    )


class FakeBleTransport:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {
            UUID_BATTERY_LEVEL: bytes([87]),
            UUID_DEVICE_NAME: b"Baseus Bowie MC2 Air\x00",
            VENDOR_UUID: bytes.fromhex("01ff"),
        }
        self.reads: list[tuple[str, str]] = []
        self.writes: list[tuple[str, str, bytes, bool]] = []

    async def scan(self, timeout: float = 5.0) -> list[BleDiscoveredDevice]:
        return [baseus_device()]

    async def read_gatt(self, address: str, char_uuid: str) -> bytes:
        self.reads.append((address, char_uuid))
        return self.values[char_uuid]

    async def write_gatt(
        self,
        address: str,
        char_uuid: str,
        data: bytes,
        *,
        response: bool = True,
    ) -> None:
        self.writes.append((address, char_uuid, data, response))


async def make_bridge(
    tmp_path: Path,
) -> tuple[BleGattBridge, FakeBleTransport, InMemoryMqttBus]:
    transport = FakeBleTransport()
    bus = InMemoryMqttBus()
    bridge = BleGattBridge(bus, transport=transport, profiles_dir=tmp_path / "profiles")
    await bridge.scan()
    profile = await bridge.build_profile(BASEUS_MAC, vendor="Baseus")
    bridge.save_profile(profile)
    return bridge, transport, bus


# ------------------------------------------------------------------ bleak (mockado)


class FakeBleakClient:
    instances: list[FakeBleakClient] = []

    def __init__(self, address: str, timeout: float = 10.0) -> None:
        self.address = address
        self.writes: list[tuple[str, bytes, bool]] = []
        char = SimpleNamespace(uuid=UUID_BATTERY_LEVEL, properties=["read", "notify"], handle=12)
        self.services = [SimpleNamespace(characteristics=[char])]
        FakeBleakClient.instances.append(self)

    async def __aenter__(self) -> FakeBleakClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def read_gatt_char(self, uuid: str) -> bytearray:
        assert uuid == UUID_BATTERY_LEVEL
        return bytearray([64])

    async def write_gatt_char(self, uuid: str, data: bytes, response: bool = True) -> None:
        self.writes.append((uuid, data, response))


class FakeBleakScanner:
    @staticmethod
    async def discover(timeout: float = 5.0, return_adv: bool = False) -> dict[str, Any]:
        device = SimpleNamespace(address=BASEUS_MAC, name="Baseus Bowie MC2 Air")
        adv = SimpleNamespace(
            local_name="Baseus Bowie MC2 Air",
            rssi=-48,
            service_uuids=["0000180F-0000-1000-8000-00805F9B34FB"],
        )
        return {BASEUS_MAC: (device, adv)}


@pytest.mark.asyncio
async def test_bleak_transport_scan_read_write_with_mocked_bleak() -> None:
    FakeBleakClient.instances.clear()
    module = SimpleNamespace(BleakScanner=FakeBleakScanner, BleakClient=FakeBleakClient)
    transport = BleakTransport(bleak_module=module)

    devices = await transport.scan(1.0)
    assert devices[0].name == "Baseus Bowie MC2 Air"
    assert devices[0].rssi == -48
    assert devices[0].service_uuids == ["0000180f-0000-1000-8000-00805f9b34fb"]

    assert await transport.read_gatt(BASEUS_MAC, "00002a19-0000-1000-8000-00805f9b34fb") == bytes(
        [64]
    )
    await transport.write_gatt(BASEUS_MAC, VENDOR_UUID, b"\x01", response=False)
    assert FakeBleakClient.instances[-1].writes == [(VENDOR_UUID, b"\x01", False)]
    chars = await transport.list_characteristics(BASEUS_MAC)
    assert chars[0].uuid == UUID_BATTERY_LEVEL and chars[0].handle == 12


@pytest.mark.asyncio
async def test_bridge_with_mocked_bleak_reads_baseus_battery_0x2a19(tmp_path: Path) -> None:
    module = SimpleNamespace(BleakScanner=FakeBleakScanner, BleakClient=FakeBleakClient)
    bus = InMemoryMqttBus()
    bridge = BleGattBridge(
        bus,
        transport=BleakTransport(bleak_module=module),
        profiles_dir=tmp_path,
    )

    devices = await bridge.scan()
    assert devices[0].name == "Baseus Bowie MC2 Air"
    profile = await bridge.build_profile(BASEUS_MAC, vendor="Baseus")
    assert profile.characteristics[0].name == "battery_level"

    event = await bridge.read_and_publish(BASEUS_MAC, "0x2A19")

    assert event.battery_pct == 64
    assert bus.messages[-1].topic == TELEMETRY_TOPIC


# ----------------------------------------------------------------------- schemas


def test_address_and_uuid_normalization_reject_topic_injection() -> None:
    assert normalize_mac("AA:BB:CC:DD:EE:FF") == BASEUS_MAC_NORM
    assert normalize_mac("aa-bb-cc-dd-ee-ff") == BASEUS_MAC_NORM
    assert format_address(BASEUS_MAC_NORM) == BASEUS_MAC
    cb_uuid = "12345678-1234-1234-1234-1234567890ab"
    assert format_address(cb_uuid) == cb_uuid.upper()
    for bad in ("aa/bb#cc", "+", "zz:zz:zz:zz:zz:zz", "aabb", ""):
        with pytest.raises(ValueError):
            normalize_mac(bad)
    assert normalize_uuid("2A19") == UUID_BATTERY_LEVEL
    assert normalize_uuid("0x2a00") == UUID_DEVICE_NAME
    assert normalize_uuid("0000FEE1-0000-1000-8000-00805F9B34FB") == VENDOR_UUID
    with pytest.raises(ValueError):
        normalize_uuid("not-a-uuid")


def test_ble_command_message_validation() -> None:
    assert BleCommandMessage(action="read", characteristic="2a19").value_hex is None
    write = BleCommandMessage(action="write", characteristic="x", value_hex="01FF")
    assert write.value_bytes() == b"\x01\xff"
    for kwargs in (
        {"action": "write", "characteristic": "x"},
        {"action": "write", "characteristic": "x", "value_hex": "abc"},
        {"action": "write", "characteristic": "x", "value_hex": "zz"},
        {"action": "read", "characteristic": "x", "value_hex": "01"},
    ):
        with pytest.raises(ValueError):
            BleCommandMessage(**kwargs)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        BleCommandMessage.model_validate({"action": "read", "characteristic": "x", "extra": 1})


# ---------------------------------------------------------------------- BLE bridge


@pytest.mark.asyncio
async def test_profile_maps_standard_and_vendor_uuids_and_roundtrips_json(tmp_path: Path) -> None:
    bridge, _, _ = await make_bridge(tmp_path)

    path = tmp_path / "profiles" / f"{BASEUS_MAC_NORM}.json"
    assert path.is_file()
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["address"] == BASEUS_MAC_NORM and stored["vendor"] == "Baseus"
    by_uuid = {item["uuid"]: item for item in stored["characteristics"]}
    assert by_uuid[UUID_BATTERY_LEVEL]["name"] == "battery_level"
    assert by_uuid[UUID_BATTERY_LEVEL]["encoding"] == "uint8"
    assert by_uuid[UUID_DEVICE_NAME]["name"] == "device_name"
    assert by_uuid[VENDOR_UUID]["name"] == "vendor_0000fee1"

    fresh = BleGattBridge(InMemoryMqttBus(), transport=FakeBleTransport())
    loaded = fresh.load_profile(BASEUS_MAC, directory=tmp_path / "profiles")
    assert isinstance(loaded, BleDeviceProfile)
    assert loaded == bridge.load_profile(path)
    assert fresh.load_profile(path).characteristics[2].writable is True
    with pytest.raises(BleBridgeError):
        fresh.load_profile("112233445566", directory=tmp_path / "profiles")
    (tmp_path / "profiles" / "bad.json").write_text("{not json", encoding="utf-8")
    assert [p.address for p in fresh.list_profiles()] == [BASEUS_MAC_NORM]
    with pytest.raises(BleBridgeError):
        BleGattBridge(InMemoryMqttBus(), transport=FakeBleTransport()).save_profile(loaded)


@pytest.mark.asyncio
async def test_registered_vendor_characteristic_gets_friendly_name(tmp_path: Path) -> None:
    bus = InMemoryMqttBus()
    bridge = BleGattBridge(bus, transport=FakeBleTransport(), profiles_dir=tmp_path)
    bridge.register_characteristic(VENDOR_UUID, "anc_mode", "uint8")
    await bridge.scan()
    profile = await bridge.build_profile(BASEUS_MAC)
    named = {c.uuid: c for c in profile.characteristics}[VENDOR_UUID]
    assert (named.name, named.encoding) == ("anc_mode", "uint8")


@pytest.mark.asyncio
async def test_read_battery_publishes_qos1_telemetry(tmp_path: Path) -> None:
    bridge, transport, bus = await make_bridge(tmp_path)

    event = await bridge.read_and_publish(BASEUS_MAC, "2a19")

    assert isinstance(event, BleTelemetryEvent)
    assert event.battery_pct == 87 and event.value == 87 and event.raw_hex == "57"
    assert event.sensitivity == "private"
    assert transport.reads == [(BASEUS_MAC, UUID_BATTERY_LEVEL)]
    message = bus.messages[-1]
    assert message.topic == TELEMETRY_TOPIC
    assert message.qos == 1 and message.retain is False
    body = json.loads(message.payload)
    assert body["name"] == "battery_level" and body["battery_pct"] == 87
    assert body["mac"] == BASEUS_MAC_NORM


@pytest.mark.asyncio
async def test_poll_once_reads_all_readable_and_sanitizes_text(tmp_path: Path) -> None:
    bridge, transport, bus = await make_bridge(tmp_path)
    transport.values[UUID_DEVICE_NAME] = "joao@example.com's buds".encode()

    events = await bridge.poll_once(BASEUS_MAC)

    assert len(events) == 3 and len(bus.messages) == 3
    name_event = next(e for e in events if e.name == "device_name")
    assert "joao@example.com" not in str(name_event.value)
    assert "[EMAIL_REDACTED]" in str(name_event.value)
    vendor_event = next(e for e in events if e.name.startswith("vendor_"))
    assert vendor_event.value == "01ff"


@pytest.mark.asyncio
async def test_cmd_write_is_limited_to_writable_profile_characteristics(tmp_path: Path) -> None:
    bridge, transport, bus = await make_bridge(tmp_path)

    payload = json.dumps({"action": "write", "characteristic": VENDOR_UUID, "value_hex": "0a0b"})
    event = await bridge.handle_mqtt_message(CMD_TOPIC, payload)

    assert event is not None and event.event == "write_ack"
    assert transport.writes == [(BASEUS_MAC, VENDOR_UUID, b"\x0a\x0b", True)]
    assert bus.messages[-1].topic == TELEMETRY_TOPIC
    assert json.loads(bus.messages[-1].payload)["raw_hex"] == "0a0b"

    read_event = await bridge.handle_command(
        BASEUS_MAC_NORM, json.dumps({"action": "read", "characteristic": "battery_level"})
    )
    assert read_event.battery_pct == 87

    with pytest.raises(BleBridgeError):
        await bridge.handle_command(
            BASEUS_MAC,
            json.dumps({"action": "write", "characteristic": "2a19", "value_hex": "01"}),
        )
    with pytest.raises(BleBridgeError):
        await bridge.handle_command(
            BASEUS_MAC,
            json.dumps({"action": "write", "characteristic": "deadbeef", "value_hex": "01"}),
        )
    with pytest.raises(BleBridgeError):
        await bridge.handle_command(
            BASEUS_MAC,
            json.dumps(
                {"action": "write", "characteristic": VENDOR_UUID, "value_hex": "00" * 300}
            ),
        )
    with pytest.raises(BleBridgeError):
        await bridge.handle_command(
            "112233445566", json.dumps({"action": "read", "characteristic": "2a19"})
        )
    assert len(transport.writes) == 1


@pytest.mark.asyncio
async def test_handle_mqtt_message_ignores_foreign_topics_and_reports_errors(
    tmp_path: Path,
) -> None:
    bridge, transport, bus = await make_bridge(tmp_path)
    before = len(bus.messages)

    assert await bridge.handle_mqtt_message("yby/other/aabbccddeeff/cmd", "{}") is None
    assert await bridge.handle_mqtt_message("yby/bridges/ble/aa+bb/cmd", "{}") is None
    assert len(bus.messages) == before

    assert await bridge.handle_mqtt_message(CMD_TOPIC, "{broken") is None
    error = json.loads(bus.messages[-1].payload)
    assert "inválido" in error["error"] and bus.messages[-1].topic == TELEMETRY_TOPIC
    assert transport.writes == []
    assert BleGattBridge.cmd_topic(BASEUS_MAC) == CMD_TOPIC


@pytest.mark.asyncio
async def test_poll_loop_runs_bounded_iterations(tmp_path: Path) -> None:
    bridge, _, bus = await make_bridge(tmp_path)
    await bridge.run_poll_loop([BASEUS_MAC, "112233445566"], interval=0, iterations=2)
    assert len(bus.messages) == 6


# --------------------------------------------------------------- traffic scrubbing

SECRET_TOKEN = "supersecrettoken123456"


def test_scrub_headers_and_payload_removes_secrets_and_pii() -> None:
    scrubbed = scrub_headers_and_payload(
        {
            "Authorization": f"Bearer {SECRET_TOKEN}",
            "Cookie": "sid=abc123",
            "Set-Cookie": "sid=abc123; HttpOnly",
            "X-API-Key": "k-123456",
            "X-Device-Token": "zzz",
            "User-Agent": "iot/1.0 contact joao@example.com",
            "Content-Type": "application/json",
        },
        {
            "temp": 21.5,
            "email": "joao@example.com",
            "password": "hunter2",
            "nested": {"access_token": SECRET_TOKEN, "note": f"token={SECRET_TOKEN}", "ok": True},
            "contact": "ligue (11) 98888-7777 ou 123.456.789-09 em 192.168.0.10",
            "mac": "AA:BB:CC:DD:EE:FF",
            "items": [{"phone": "11988887777"}, "Bearer abcdef123456"],
        },
    )

    dumped = json.dumps({"h": scrubbed.headers, "p": scrubbed.payload})
    for leaked in (
        SECRET_TOKEN,
        "abc123",
        "k-123456",
        "joao@example.com",
        "hunter2",
        "98888-7777",
        "123.456.789-09",
        "192.168.0.10",
        "AA:BB:CC:DD:EE:FF",
        "abcdef123456",
    ):
        assert leaked not in dumped
    assert scrubbed.headers["Authorization"] == "[REDACTED]"
    assert scrubbed.headers["Cookie"] == "[REDACTED]"
    assert scrubbed.headers["Content-Type"] == "application/json"
    assert scrubbed.payload["temp"] == 21.5
    assert scrubbed.payload["nested"]["ok"] is True
    assert scrubbed.redactions >= 10


def test_is_local_host_only_accepts_lan_names() -> None:
    for host in ("192.168.1.20", "10.0.0.5", "127.0.0.1", "[::1]", "esp-sensor.local", "plug"):
        assert is_local_host(host)
    for host in ("8.8.8.8", "api.vendor.com", "", "example.org"):
        assert not is_local_host(host)
    assert is_local_host("api.vendor.com", extra_hosts=["API.vendor.com"])


# ------------------------------------------------------------------- mitmproxy addon


class FakeHeaders(dict[str, str]):
    pass


def http_flow(
    *,
    host: str = "192.168.1.50",
    path: str = "/api/state?token=abc",
    body: str | None = None,
    status_code: int = 200,
) -> Any:
    payload = body
    if payload is None:
        payload = json.dumps(
            {
                "door": {"state": "open"},
                "temp": 31,
                "token": SECRET_TOKEN,
                "owner": "joao@example.com",
            }
        )
    request = SimpleNamespace(
        host=host,
        pretty_host=host,
        method="GET",
        path=path,
        headers=FakeHeaders({"Authorization": f"Bearer {SECRET_TOKEN}", "Cookie": "sid=abc"}),
    )
    response = SimpleNamespace(
        status_code=status_code,
        headers=FakeHeaders({"Set-Cookie": "sid=zzz", "Content-Type": "application/json"}),
        get_text=lambda strict=False: payload,
    )
    return SimpleNamespace(request=request, response=response)


def ws_flow(text: str, *, host: str = "192.168.1.60", from_client: bool = False) -> Any:
    message = SimpleNamespace(is_text=True, text=text, from_client=from_client)
    request = SimpleNamespace(
        host=host,
        pretty_host=host,
        path="/ws",
        headers=FakeHeaders({"Authorization": f"Bearer {SECRET_TOKEN}"}),
    )
    return SimpleNamespace(request=request, websocket=SimpleNamespace(messages=[message]))


def alert_rule() -> TrafficAlertRule:
    return TrafficAlertRule(
        name="door_open",
        message="Porta aberta",
        json_path="door.state",
        equals="open",
        haptic=True,
    )


@pytest.mark.asyncio
async def test_addon_http_response_redacts_and_publishes_event_and_twatch_alert() -> None:
    bus = InMemoryMqttBus()
    addon = YbyTrafficAddon(bus, source="door-sensor", alert_rules=[alert_rule()])

    await addon.response(http_flow())

    topics = [m.topic for m in bus.messages]
    assert topics == [
        "yby/bridges/traffic/door-sensor/event",
        TOPIC_TWATCH_CMD,
        TOPIC_TWATCH_CMD,
    ]
    assert all(m.qos == 1 for m in bus.messages)
    everything = "\n".join(m.payload for m in bus.messages)
    for leaked in (SECRET_TOKEN, "sid=abc", "sid=zzz", "joao@example.com", "192.168.1.50"):
        assert leaked not in everything

    event = NormalizedTrafficEvent.model_validate_json(bus.messages[0].payload)
    assert event.sensitivity == "private" and event.protocol == "http"
    assert event.headers["Set-Cookie"] == "[REDACTED]"
    assert event.payload["token"] == "[REDACTED]"
    assert event.payload["door"]["state"] == "open"
    assert event.path == "/api/state"
    assert event.host.startswith("host-")
    assert event.alerts == ["door_open"] and event.redactions >= 3

    display = TWatchCommand.model_validate_json(bus.messages[1].payload)
    assert display.command == "display_text" and display.text == "Porta aberta"
    assert display.accent_color == "#00FF66"
    assert TWatchCommand.model_validate_json(bus.messages[2].payload).command == "haptic_pulse"
    assert addon.events[-1].alerts == ["door_open"]


@pytest.mark.asyncio
async def test_addon_ignores_internet_hosts_and_non_json() -> None:
    bus = InMemoryMqttBus()
    addon = YbyTrafficAddon(bus, alert_rules=[alert_rule()])

    await addon.response(http_flow(host="api.vendor.com"))
    await addon.response(http_flow(body="<html>not json</html>"))
    await addon.response(http_flow(body="42"))
    await addon.response(SimpleNamespace(request=http_flow().request, response=None))
    await addon.websocket_message(ws_flow("plain text"))
    await addon.websocket_message(ws_flow('{"x":1}', host="cloud.vendor.com"))

    assert bus.messages == []


@pytest.mark.asyncio
async def test_addon_websocket_message_normalizes_and_alerts_only_on_match() -> None:
    bus = InMemoryMqttBus()
    rule = TrafficAlertRule(name="hot", message="Quente!", json_path="temp", gt=30)
    addon = YbyTrafficAddon(bus, source="plug", alert_rules=[rule])

    await addon.websocket_message(ws_flow(json.dumps({"temp": 20, "api_key": SECRET_TOKEN})))
    assert [m.topic for m in bus.messages] == ["yby/bridges/traffic/plug/event"]

    await addon.websocket_message(
        ws_flow(json.dumps({"temp": 35, "password": "x", "mac": "AA:BB:CC:DD:EE:FF"}))
    )
    topics = [m.topic for m in bus.messages]
    assert topics[1:] == ["yby/bridges/traffic/plug/event", TOPIC_TWATCH_CMD]
    event = NormalizedTrafficEvent.model_validate_json(bus.messages[1].payload)
    assert event.protocol == "ws" and event.direction == "server"
    assert event.payload["password"] == "[REDACTED]"
    assert "AA:BB:CC:DD:EE:FF" not in bus.messages[1].payload
    assert SECRET_TOKEN not in "\n".join(m.payload for m in bus.messages)
    assert json.loads(bus.messages[2].payload)["text"] == "Quente!"


def test_alert_rule_validation_and_matching_edge_cases() -> None:
    with pytest.raises(ValueError):
        TrafficAlertRule(name="empty")
    with pytest.raises(ValueError):
        TrafficAlertRule(name="bad", host_contains="x", gt=1)
    assert TrafficAlertRule(name="n", contains="x").alert_text == "n"


@pytest.mark.asyncio
async def test_addon_auto_source_is_pseudonymous() -> None:
    bus = InMemoryMqttBus()
    addon = YbyTrafficAddon(bus, alert_rules=[])
    await addon.response(http_flow(host="esp-sensor.local", body='{"a": 1}'))
    assert bus.messages[0].topic == "yby/bridges/traffic/esp-sensor-local/event"
    await addon.response(http_flow(host="192.168.1.77", body='{"a": 1}'))
    assert bus.messages[1].topic.startswith("yby/bridges/traffic/host-")
    assert "192.168.1.77" not in bus.messages[1].topic


# ------------------------------------------------------------------------- ADB


class FakeAdbRunner:
    def __init__(self, outputs: dict[str, tuple[int, str]]) -> None:
        self.outputs = outputs
        self.commands: list[list[str]] = []

    async def run(
        self,
        argv: Sequence[str],
        *,
        stdin_bytes: bytes | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, bytes, bytes]:
        self.commands.append(list(argv))
        for marker, (code, out) in self.outputs.items():
            if marker in argv:
                return code, out.encode(), b"adb: error token=" + SECRET_TOKEN.encode()
        return 1, b"", b"unexpected"


LOGCAT = "\n".join(
    [
        "I/YBY      ( 1234): " + json.dumps(
            {"door": {"state": "open"}, "Authorization": f"Bearer {SECRET_TOKEN}"}
        ),
        f"D/Termux   ( 1300): sync ok for joao@example.com token={SECRET_TOKEN}",
        "I/ChromiumNet( 999): GET https://private.example/secret",
        "--------- beginning of main",
        "garbage line",
    ]
)
BATTERY = (
    "Current Battery Service state:\n  AC powered: false\n  USB powered: true\n"
    "  status: 2\n  level: 83\n  temperature: 301\n"
)


@pytest.mark.asyncio
async def test_adb_bridge_normalizes_logcat_battery_and_dispatches_twatch_alert() -> None:
    bus = InMemoryMqttBus()
    runner = FakeAdbRunner({"logcat": (0, LOGCAT), "dumpsys": (0, BATTERY)})
    bridge = AdbEventBridge(
        bus,
        runner=runner,
        serial="R5CT123ABC",
        alert_rules=[alert_rule()],
    )

    events = await bridge.poll_once()

    assert runner.commands[0] == [
        "adb", "-s", "R5CT123ABC", "logcat", "-d", "-v", "brief", "-t", "200"
    ]
    assert runner.commands[1][-3:] == ["shell", "dumpsys", "battery"]
    assert len(events) == 3
    assert all(isinstance(e, NormalizedTrafficEvent) and e.sensitivity == "private" for e in events)
    assert {e.path for e in events} == {"YBY", "Termux", "battery"}
    battery = events[-1]
    assert battery.payload["level"] == 83 and battery.payload["charging"] is True

    event_topics = [m.topic for m in bus.messages if m.topic.startswith("yby/bridges")]
    assert set(event_topics) == {"yby/bridges/traffic/xiaomi12/event"}
    everything = "\n".join(m.payload for m in bus.messages)
    for leaked in (SECRET_TOKEN, "joao@example.com", "ChromiumNet", "private.example"):
        assert leaked not in everything
    alerts = [m for m in bus.messages if m.topic == TOPIC_TWATCH_CMD]
    assert len(alerts) == 2
    assert TWatchCommand.model_validate_json(alerts[0].payload).accent_color == "#00FF66"


@pytest.mark.asyncio
async def test_adb_bridge_event_file_and_safety_checks() -> None:
    bus = InMemoryMqttBus()
    jsonl = '{"kind":"sync","password":"x"}\nnot json\n{"kind":"ok"}\n'
    runner = FakeAdbRunner({"tail": (0, jsonl), "logcat": (1, "")})
    bridge = AdbEventBridge(bus, runner=runner)

    events = await bridge.collect_event_file("/sdcard/Download/yby-events.jsonl", max_lines=5)
    assert [e.payload.get("kind") for e in events] == ["sync", "ok"]
    assert events[0].payload["password"] == "[REDACTED]"
    assert runner.commands[-1][-3:] == ["-n", "5", "/sdcard/Download/yby-events.jsonl"]

    for bad in (
        "/data/data/com.termux/files/home/x",
        "/sdcard/../etc/passwd",
        "/sdcard/a;rm -rf /",
    ):
        with pytest.raises(TrafficBridgeError):
            await bridge.collect_event_file(bad)
    with pytest.raises(TrafficBridgeError) as failure:
        await bridge.collect_logcat()
    assert SECRET_TOKEN not in str(failure.value)
    with pytest.raises(TrafficBridgeError):
        AdbEventBridge(bus, runner=runner, serial="bad serial; reboot")
    with pytest.raises(TrafficBridgeError):
        await AdbEventBridge(
            bus, runner=FakeAdbRunner({"dumpsys": (0, "nothing")})
        ).collect_battery()

    for command in runner.commands:
        assert command[0] == "adb"
        assert not {"su", "frida", "root", "install", "push"} & set(command)


# --------------------------------------------------------------------- app mounts


@pytest.mark.asyncio
async def test_mesh_app_mounts_protected_ble_profiles_and_rea_diff(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from src.yby.app import create_mesh_app

    bridge, _, _ = await make_bridge(tmp_path)
    firmware = tmp_path / "firmware"
    firmware.mkdir()
    (firmware / "factory.bin").write_bytes(b"\x00" * 8192)
    (firmware / "custom.bin").write_bytes(b"\x00" * 4096 + b"\x01" * 4096)
    (tmp_path / "outside.bin").write_bytes(b"\x00")
    auth = {"Authorization": "Bearer mesh-token"}

    app = create_mesh_app(
        expected_token="mesh-token",
        ble_bridge=bridge,
        rea_enabled=True,
        rea_firmware_root=firmware,
    )
    client = TestClient(app)

    assert client.get("/health").json()["modules"]["ble_bridge"] is True
    assert client.get("/bridges/ble/profiles").status_code == 401
    listing = client.get("/bridges/ble/profiles", headers=auth)
    assert listing.status_code == 200
    assert listing.json()["profiles"][0]["address"] == BASEUS_MAC_NORM

    body = {"base_bin": "factory.bin", "target_bin": "custom.bin"}
    assert client.post("/rea/diff", json=body).status_code == 401
    diff = client.post("/rea/diff", json=body, headers=auth)
    assert diff.status_code == 200
    report = diff.json()
    assert report["sensitivity"] == "private" and report["origin"] == "rea_artifact"
    assert report["report"]["changed_blocks"] == 1
    assert report["report"]["identical"] is False

    outside = {"base_bin": "../outside.bin", "target_bin": "custom.bin"}
    assert client.post("/rea/diff", json=outside, headers=auth).status_code == 403
    missing = {"base_bin": "nope.bin", "target_bin": "custom.bin"}
    assert client.post("/rea/diff", json=missing, headers=auth).status_code == 404

    plain = TestClient(create_mesh_app(expected_token="mesh-token"))
    assert plain.get("/bridges/ble/profiles", headers=auth).status_code == 404
    assert plain.post("/rea/diff", json=body, headers=auth).status_code == 404
    assert plain.get("/health").json()["modules"]["rea"] is False
