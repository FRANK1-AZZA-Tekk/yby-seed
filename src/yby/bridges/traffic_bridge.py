"""Ponte passiva de telemetria IoT local (HTTP/WebSocket e ADB/Termux) -> MQTT.

Uso estritamente defensivo e somente leitura, para QA e interoperabilidade local com
dispositivos do próprio usuário. Não há bypass de SSL pinning, injeção Frida ou
adulteração de tráfego: o addon apenas observa fluxos que o mitmproxy já recebeu e o
`AdbEventBridge` só executa comandos `adb` de leitura de uma allowlist fixa.

Antes de qualquer armazenamento ou publicação MQTT, cabeçalhos e payloads passam por
`scrub_headers_and_payload` (Authorization, cookies, tokens e PII via `sanitize_for_cloud`).
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.security.cloud_sanitizer import sanitize_for_cloud
from src.yby.audio.device import CommandRunner, SubprocessCommandRunner
from src.yby.audio.mqtt_bus import MqttPublisher
from src.yby.audio.schemas import TOPIC_TWATCH_CMD, TWatchCommand
from src.yby.bridges.schemas import (
    TOPIC_TRAFFIC_EVENT,
    NormalizedTrafficEvent,
    TrafficAlertRule,
    normalize_source,
)

REDACTED = "[REDACTED]"
MAC_REDACTED = "[MAC_REDACTED]"
MAX_TEXT = 512
MAX_ITEMS = 50
MAX_DEPTH = 6

_SENSITIVE_HEADER_NAMES = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
        "apikey",
        "x-auth-token",
        "x-access-token",
        "x-csrf-token",
        "x-xsrf-token",
        "x-amz-security-token",
        "x-forwarded-for",
        "x-real-ip",
    }
)
_SENSITIVE_HEADER_FRAGMENTS = ("token", "secret", "session", "password", "credential")
_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "bearer",
        "cookie",
        "set_cookie",
        "password",
        "passwd",
        "pass",
        "pwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "auth_token",
        "api_key",
        "apikey",
        "session",
        "session_id",
        "sessionid",
        "sid",
        "email",
        "e_mail",
        "phone",
        "mobile",
        "cpf",
        "cnpj",
        "latitude",
        "longitude",
        "lat",
        "lon",
        "lng",
        "gps",
        "location",
        "address",
    }
)
_MAC_PATTERN = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
_LOCAL_SUFFIXES = (".local", ".lan", ".home.arpa", ".internal", ".localdomain")
_BATTERY_KEYS = frozenset({"level", "status", "ac_powered", "usb_powered", "temperature"})
_ADB_SERIAL = re.compile(r"^[A-Za-z0-9._:\-]{1,64}$")
_LOGCAT_BRIEF = re.compile(r"^([VDIWEF])/(\S+?)\s*\(\s*(\d+)\):\s?(.*)$")
_REMOTE_EVENT_PATH = re.compile(r"^(?:/sdcard|/storage/emulated/0)/[A-Za-z0-9._/\-]{1,200}$")


class TrafficBridgeError(RuntimeError):
    """Falha controlada na ponte de tráfego/ADB."""


@dataclass(frozen=True)
class ScrubbedTraffic:
    headers: dict[str, str]
    payload: Any
    redactions: int


def _normalize_key(key: str) -> str:
    return key.strip().casefold().replace("-", "_").replace(" ", "_")


def _is_sensitive_header(name: str) -> bool:
    lowered = name.strip().casefold()
    return lowered in _SENSITIVE_HEADER_NAMES or any(
        fragment in lowered for fragment in _SENSITIVE_HEADER_FRAGMENTS
    )


def scrub_text(text: str) -> tuple[str, int]:
    """Redige segredos/PII (via `sanitize_for_cloud`) e endereços MAC de um texto."""

    clipped = text[:MAX_TEXT]
    result = sanitize_for_cloud(clipped, environ={"YBY_CLOUD_SANITIZE": "1"})
    cleaned, macs = _MAC_PATTERN.subn(MAC_REDACTED, result.text)
    return cleaned, result.redactions + macs


def _scrub_value(value: Any, depth: int = 0) -> tuple[Any, int]:
    if depth > MAX_DEPTH:
        return REDACTED, 1
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        count = 0
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_ITEMS:
                break
            key_text = str(key)[:64]
            if _normalize_key(key_text) in _SENSITIVE_KEYS:
                out[key_text] = REDACTED
                count += 1
                continue
            cleaned, n = _scrub_value(item, depth + 1)
            out[key_text] = cleaned
            count += n
        return out, count
    if isinstance(value, (list, tuple)):
        items: list[Any] = []
        count = 0
        for item in list(value)[:MAX_ITEMS]:
            cleaned, n = _scrub_value(item, depth + 1)
            items.append(cleaned)
            count += n
        return items, count
    if isinstance(value, bytes):
        return scrub_text(value.decode("utf-8", errors="replace"))
    if value is None or isinstance(value, (bool, int, float)):
        return value, 0
    return scrub_text(str(value))


def scrub_headers_and_payload(
    headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
    payload: Any = None,
) -> ScrubbedTraffic:
    """Remove Authorization/Cookie/tokens/PII de cabeçalhos e payload antes de emitir."""

    items = headers.items() if isinstance(headers, Mapping) else (headers or [])
    clean_headers: dict[str, str] = {}
    redactions = 0
    for name, value in items:
        name_text = str(name)[:64]
        if _is_sensitive_header(name_text):
            clean_headers[name_text] = REDACTED
            redactions += 1
            continue
        cleaned, count = scrub_text(str(value))
        clean_headers[name_text] = cleaned
        redactions += count
    clean_payload, payload_redactions = _scrub_value(payload)
    return ScrubbedTraffic(clean_headers, clean_payload, redactions + payload_redactions)


def is_local_host(host: str, extra_hosts: Iterable[str] = ()) -> bool:
    """True para IPs privados/loopback/link-local e nomes de rede local (não internet)."""

    value = host.strip().strip("[]").casefold()
    if not value:
        return False
    if value in {h.casefold() for h in extra_hosts}:
        return True
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return value.endswith(_LOCAL_SUFFIXES) or "." not in value
    return address.is_private or address.is_loopback or address.is_link_local


def _host_label(host: str) -> str:
    """Pseudonimiza IPs locais (hash curto) e mantém nomes de host já sanitizados."""

    value = host.strip().strip("[]")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return scrub_text(value)[0][:128]
    return f"host-{hashlib.sha256(value.encode()).hexdigest()[:8]}"


def _json_lookup(payload: Any, dotted: str) -> tuple[bool, Any]:
    current = payload
    for part in dotted.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return False, None
    return True, current


def rule_matches(rule: TrafficAlertRule, event: NormalizedTrafficEvent) -> bool:
    """Avalia a regra apenas sobre o evento já sanitizado."""

    if rule.host_contains and rule.host_contains.casefold() not in event.host.casefold():
        return False
    if rule.path_contains and rule.path_contains.casefold() not in event.path.casefold():
        return False
    found, value = (True, None)
    if rule.json_path:
        found, value = _json_lookup(event.payload, rule.json_path)
        if not found:
            return False
        if rule.equals is not None and value != rule.equals:
            return False
        if rule.gt is not None or rule.lt is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return False
            if rule.gt is not None and not value > rule.gt:
                return False
            if rule.lt is not None and not value < rule.lt:
                return False
    if rule.contains:
        haystack = json.dumps(event.payload, ensure_ascii=False, default=str) + event.text_summary
        if rule.contains.casefold() not in haystack.casefold():
            return False
    return True


class TrafficEmitter:
    """Publica eventos normalizados (QoS 1), guarda um buffer circular e dispara alertas."""

    def __init__(
        self,
        publisher: MqttPublisher,
        *,
        alert_rules: Sequence[TrafficAlertRule] = (),
        max_recent: int = 200,
    ) -> None:
        self._publisher = publisher
        self.alert_rules = list(alert_rules)
        self.recent: deque[NormalizedTrafficEvent] = deque(maxlen=max_recent)

    async def emit(self, event: NormalizedTrafficEvent) -> NormalizedTrafficEvent:
        matched = [rule for rule in self.alert_rules if rule_matches(rule, event)]
        event = event.model_copy(update={"alerts": [rule.name for rule in matched]})
        self.recent.append(event)
        await self._publisher.publish(
            TOPIC_TRAFFIC_EVENT.format(source=event.source),
            event.model_dump_json(),
            qos=1,
            retain=False,
        )
        for rule in matched:
            await self._publisher.publish(
                TOPIC_TWATCH_CMD,
                TWatchCommand(
                    command="display_text",
                    text=rule.alert_text,
                    accent_color="#00FF66",
                ).model_dump_json(),
                qos=1,
                retain=False,
            )
            if rule.haptic:
                await self._publisher.publish(
                    TOPIC_TWATCH_CMD,
                    TWatchCommand(command="haptic_pulse", accent_color="#00FF66").model_dump_json(),
                    qos=1,
                    retain=False,
                )
        return event


def _decode_body(message: Any) -> str:
    getter = getattr(message, "get_text", None)
    if callable(getter):
        try:
            return str(getter(strict=False) or "")
        except TypeError:
            return str(getter() or "")
    content = getattr(message, "content", b"") or b""
    return content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)


def _parse_json(text: str) -> Any | None:
    if not text.strip():
        return None
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, RecursionError):
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


class YbyTrafficAddon:
    """Addon compatível com mitmproxy (`response`, `websocket_message`), passivo e local."""

    def __init__(
        self,
        publisher: MqttPublisher,
        *,
        source: str | None = None,
        alert_rules: Sequence[TrafficAlertRule] = (),
        extra_local_hosts: Iterable[str] = (),
    ) -> None:
        self._source = normalize_source(source) if source else None
        self._extra_hosts = tuple(extra_local_hosts)
        self.emitter = TrafficEmitter(publisher, alert_rules=alert_rules)

    @property
    def events(self) -> list[NormalizedTrafficEvent]:
        return list(self.emitter.recent)

    def _source_for(self, host: str) -> str:
        return self._source or normalize_source(_host_label(host).lower().replace(".", "-")[:32])

    def normalize_http_flow(self, flow: Any) -> NormalizedTrafficEvent | None:
        request = getattr(flow, "request", None)
        response = getattr(flow, "response", None)
        if request is None or response is None:
            return None
        host = str(getattr(request, "pretty_host", None) or getattr(request, "host", ""))
        if not is_local_host(host, self._extra_hosts):
            return None
        parsed = _parse_json(_decode_body(response))
        if parsed is None:
            return None
        scrubbed = scrub_headers_and_payload(getattr(response, "headers", None), parsed)
        path = scrub_text(str(getattr(request, "path", "")).split("?", 1)[0])[0][:256]
        return NormalizedTrafficEvent(
            source=self._source_for(host),
            protocol="http",
            host=_host_label(host),
            method=str(getattr(request, "method", ""))[:16],
            path=path,
            status_code=getattr(response, "status_code", None),
            direction="response",
            headers=scrubbed.headers,
            payload=scrubbed.payload,
            redactions=scrubbed.redactions,
        )

    def normalize_ws_flow(self, flow: Any) -> NormalizedTrafficEvent | None:
        websocket = getattr(flow, "websocket", None)
        request = getattr(flow, "request", None)
        messages = getattr(websocket, "messages", None)
        if not messages or request is None:
            return None
        host = str(getattr(request, "pretty_host", None) or getattr(request, "host", ""))
        if not is_local_host(host, self._extra_hosts):
            return None
        message = messages[-1]
        if not getattr(message, "is_text", True):
            return None
        raw = getattr(message, "text", None)
        if raw is None:
            content = getattr(message, "content", b"")
            raw = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else ""
        parsed = _parse_json(str(raw))
        if parsed is None:
            return None
        scrubbed = scrub_headers_and_payload(getattr(request, "headers", None), parsed)
        path = scrub_text(str(getattr(request, "path", "")).split("?", 1)[0])[0][:256]
        return NormalizedTrafficEvent(
            source=self._source_for(host),
            protocol="ws",
            host=_host_label(host),
            method="WS",
            path=path,
            direction="client" if getattr(message, "from_client", False) else "server",
            headers=scrubbed.headers,
            payload=scrubbed.payload,
            redactions=scrubbed.redactions,
        )

    async def response(self, flow: Any) -> None:
        event = self.normalize_http_flow(flow)
        if event is not None:
            await self.emitter.emit(event)

    async def websocket_message(self, flow: Any) -> None:
        event = self.normalize_ws_flow(flow)
        if event is not None:
            await self.emitter.emit(event)


class AdbEventBridge:
    """Ponte ADB/Termux somente leitura (Xiaomi 12): logcat filtrado, bateria e arquivo JSONL."""

    def __init__(
        self,
        publisher: MqttPublisher,
        *,
        runner: CommandRunner | None = None,
        serial: str | None = None,
        source: str = "xiaomi12",
        adb_bin: str = "adb",
        allowed_tags: Sequence[str] = ("YBY", "Termux"),
        alert_rules: Sequence[TrafficAlertRule] = (),
    ) -> None:
        if serial is not None and not _ADB_SERIAL.match(serial):
            raise TrafficBridgeError("serial ADB inválido")
        self._runner = runner or SubprocessCommandRunner()
        self._serial = serial
        self._source = normalize_source(source)
        self._adb = adb_bin
        self._allowed_tags = tuple(tag.casefold() for tag in allowed_tags)
        self.emitter = TrafficEmitter(publisher, alert_rules=alert_rules)

    def _argv(self, *args: str) -> list[str]:
        base = [self._adb]
        if self._serial:
            base += ["-s", self._serial]
        return base + list(args)

    async def _adb_text(self, *args: str, timeout: float = 20.0) -> str:
        try:
            code, stdout, stderr = await self._runner.run(self._argv(*args), timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            raise TrafficBridgeError(f"adb indisponível: {exc}") from exc
        if code != 0:
            detail = scrub_text(stderr.decode("utf-8", errors="replace"))[0][:160]
            raise TrafficBridgeError(f"adb falhou ({code}): {detail}")
        return stdout.decode("utf-8", errors="replace")

    def _event(self, *, method: str, path: str, payload: Any) -> NormalizedTrafficEvent:
        scrubbed = scrub_headers_and_payload(None, payload)
        return NormalizedTrafficEvent(
            source=self._source,
            protocol="adb",
            host=self._source,
            method=method[:16],
            path=path[:256],
            direction="device",
            payload=scrubbed.payload,
            redactions=scrubbed.redactions,
        )

    async def collect_logcat(self, max_lines: int = 200) -> list[NormalizedTrafficEvent]:
        """Despeja o logcat (`-d`, leitura) e emite só linhas das tags permitidas."""

        text = await self._adb_text(
            "logcat", "-d", "-v", "brief", "-t", str(max(1, min(max_lines, 2000)))
        )
        emitted: list[NormalizedTrafficEvent] = []
        for line in text.splitlines():
            match = _LOGCAT_BRIEF.match(line.strip())
            if match is None:
                continue
            level, tag, _pid, message = match.groups()
            if self._allowed_tags and tag.casefold() not in self._allowed_tags:
                continue
            parsed = _parse_json(message)
            payload: Any = parsed if parsed is not None else {"message": message}
            emitted.append(
                await self.emitter.emit(self._event(method=level, path=tag, payload=payload))
            )
        return emitted

    async def collect_battery(self) -> NormalizedTrafficEvent:
        """Telemetria de bateria via `dumpsys battery` (comando fixo de leitura)."""

        text = await self._adb_text("shell", "dumpsys", "battery")
        fields: dict[str, Any] = {}
        for line in text.splitlines():
            key, sep, value = line.partition(":")
            key, value = key.strip().lower().replace(" ", "_"), value.strip()
            if not sep or key not in _BATTERY_KEYS:
                continue
            if value.lstrip("-").isdigit():
                fields[key] = int(value)
            elif value in {"true", "false"}:
                fields[key] = value == "true"
        if "level" not in fields:
            raise TrafficBridgeError("saída de dumpsys battery sem nível")
        fields["charging"] = bool(
            fields.get("ac_powered") or fields.get("usb_powered") or fields.get("status") == 2
        )
        return await self.emitter.emit(self._event(method="GET", path="battery", payload=fields))

    async def collect_event_file(
        self,
        remote_path: str,
        max_lines: int = 100,
    ) -> list[NormalizedTrafficEvent]:
        """Lê as últimas linhas de um JSONL em armazenamento compartilhado (ex.: Termux)."""

        if not _REMOTE_EVENT_PATH.match(remote_path) or ".." in remote_path:
            raise TrafficBridgeError("caminho remoto fora de /sdcard ou /storage/emulated/0")
        text = await self._adb_text(
            "shell", "tail", "-n", str(max(1, min(max_lines, 1000))), remote_path
        )
        emitted: list[NormalizedTrafficEvent] = []
        for line in text.splitlines():
            parsed = _parse_json(line)
            if parsed is None:
                continue
            emitted.append(
                await self.emitter.emit(self._event(method="EVENT", path="termux", payload=parsed))
            )
        return emitted

    async def poll_once(self) -> list[NormalizedTrafficEvent]:
        events = await self.collect_logcat()
        events.append(await self.collect_battery())
        return events
