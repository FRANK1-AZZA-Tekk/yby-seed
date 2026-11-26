"""Validação Hardware-in-the-Loop (HIL) automatizada da malha YBY de 4 nós.

Executa em 4 etapas no PC Hub (Ubuntu 26.04 LTS):
1. Diagnóstico dos 4 nós (PC Hub, Baseus Bowie MC2 Air, Xiaomi 12, LILYGO T-Watch S3 Plus).
2. Backup preventivo de 16 MB da flash do T-Watch S3 Plus com manifesto SHA-256.
3. Teste ponta a ponta da malha (Privacy Gate, failover Xiaomi 12, áudio/MQTT, yby_machine e T-Watch).
4. Tabela final limpa com status OK ou PENDENTE por nó e ajustes faltantes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import socket
import sys
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

from scripts.twatch.backup import run_backup, verify_backup_sha256
from scripts.twatch.common import (
    DEFAULT_BACKUP_DIR,
    Runner,
    default_runner,
    resolve_port,
)
from src.yby.audio.device import CommandRunner, PipeWireBluetoothDevice, SubprocessCommandRunner
from src.yby.audio.mqtt_bus import MqttPublisher, PahoMqttPublisher
from src.yby.audio.schemas import (
    TOPIC_AUDIO_STATE,
    TOPIC_TWATCH_CMD,
    TOPIC_TWATCH_TELEMETRY,
    AudioStateEvent,
    TWatchCommand,
    TWatchVoiceEnvelope,
)
from src.yby.audio.twatch_bridge import TWatchBridge
from src.yby.routing.cache import InMemoryCacheBackend, NodeHealthTracker
from src.yby.routing.privacy_gate import PrivacyGate
from src.yby.routing.router import PC_HUB_NODE, CognitiveRouter, RouterConfig
from src.yby.routing.schemas import RouteRequest, RouteTier

OFFICIAL_NODES: tuple[str, ...] = (
    "PC Hub",
    "Baseus Bowie MC2 Air",
    "Xiaomi 12",
    "LILYGO T-Watch S3 Plus",
)


@dataclass(frozen=True)
class HilQaConfig:
    """Parâmetros de rede, portas e dispositivos para o QA HIL dos 4 nós."""

    pg_dsn: str = ""
    redis_url: str = "redis://127.0.0.1:6379/0"
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_user: str | None = None
    mqtt_pass: str | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"
    litellm_base_url: str = "http://127.0.0.1:4000"
    litellm_master_key: str = ""
    mesh_base_url: str = "http://127.0.0.1:8000"
    machine_base_url: str = "http://127.0.0.1:8001"
    pocketpal_base_url: str = "http://100.64.0.2:8080/v1"
    pocketpal_model: str = "qwen2.5-coder-3b-instruct"
    edge_sync_token: str = ""
    bt_device_name: str = "Baseus Bowie MC2 Air"
    twatch_port: str | None = None
    twatch_backup_dir: Path = DEFAULT_BACKUP_DIR
    timeout_seconds: float = 4.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> HilQaConfig:
        src = environ if environ is not None else os.environ
        mqtt_port_raw = src.get("YBY_MQTT_PORT", "1883").strip()
        try:
            mqtt_port = int(mqtt_port_raw) if mqtt_port_raw else 1883
        except ValueError:
            mqtt_port = 1883

        timeout_raw = src.get("YBY_HIL_TIMEOUT", "4.0").strip()
        try:
            timeout_seconds = float(timeout_raw) if timeout_raw else 4.0
        except ValueError:
            timeout_seconds = 4.0

        backup_dir_raw = src.get("YBY_TWATCH_BACKUP_DIR", "").strip()
        backup_dir = Path(backup_dir_raw) if backup_dir_raw else DEFAULT_BACKUP_DIR

        return cls(
            pg_dsn=(
                src.get("YBY_PGVECTOR_DSN") or src.get("YBY_DATABASE_URL") or ""
            ).strip(),
            redis_url=src.get("YBY_REDIS_URL", "redis://127.0.0.1:6379/0").strip()
            or "redis://127.0.0.1:6379/0",
            mqtt_host=src.get("YBY_MQTT_HOST", "127.0.0.1").strip() or "127.0.0.1",
            mqtt_port=mqtt_port,
            mqtt_user=src.get("YBY_MQTT_USER", "").strip() or None,
            mqtt_pass=src.get("YBY_MQTT_PASS", "").strip() or None,
            ollama_base_url=(
                src.get("YBY_OLLAMA_BASE_URL")
                or src.get("OLLAMA_API_BASE")
                or "http://127.0.0.1:11434"
            )
            .strip()
            .rstrip("/"),
            litellm_base_url=src.get("YBY_LITELLM_BASE_URL", "http://127.0.0.1:4000")
            .strip()
            .rstrip("/"),
            litellm_master_key=src.get("LITELLM_MASTER_KEY", "").strip(),
            mesh_base_url=src.get("YBY_MESH_BASE_URL", "http://127.0.0.1:8000")
            .strip()
            .rstrip("/"),
            machine_base_url=src.get("YBY_MACHINE_BASE_URL", "http://127.0.0.1:8001")
            .strip()
            .rstrip("/"),
            pocketpal_base_url=src.get("YBY_POCKETPAL_BASE_URL", "http://100.64.0.2:8080/v1")
            .strip()
            .rstrip("/"),
            pocketpal_model=src.get("YBY_POCKETPAL_MODEL", "qwen2.5-coder-3b-instruct").strip()
            or "qwen2.5-coder-3b-instruct",
            edge_sync_token=(
                src.get("YBY_EDGE_SYNC_TOKEN") or src.get("GATEWAY_TOKEN") or ""
            ).strip(),
            bt_device_name=src.get("YBY_AUDIO_BT_DEVICE", "Baseus Bowie MC2 Air").strip()
            or "Baseus Bowie MC2 Air",
            twatch_port=resolve_port(None) if environ is None else (src.get("YBY_TWATCH_PORT") or "").strip() or None,
            twatch_backup_dir=backup_dir,
            timeout_seconds=max(0.5, timeout_seconds),
        )


@dataclass(frozen=True)
class CheckResult:
    node: str
    check: str
    ok: bool
    detail: str
    remediation: str = ""


@dataclass
class NodeSummary:
    node: str
    status: str
    checks: list[CheckResult] = field(default_factory=list)
    remediations: list[str] = field(default_factory=list)


@dataclass
class HilQaReport:
    nodes: dict[str, NodeSummary]
    backup_bin: str | None = None
    backup_sha256: str | None = None

    @property
    def all_ok(self) -> bool:
        return all(summary.status == "OK" for summary in self.nodes.values())

    def to_markdown_table(self) -> str:
        lines = [
            "| Nó | Status | O que falta ajustar |",
            "| --- | --- | --- |",
        ]
        for node_name in OFFICIAL_NODES:
            summary = self.nodes[node_name]
            adjustment = "; ".join(summary.remediations) if summary.remediations else "-"
            lines.append(f"| {summary.node} | {summary.status} | {adjustment} |")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_ok": self.all_ok,
            "backup_bin": self.backup_bin,
            "backup_sha256": self.backup_sha256,
            "nodes": {
                name: {
                    "status": s.status,
                    "remediations": s.remediations,
                    "checks": [
                        {
                            "check": c.check,
                            "ok": c.ok,
                            "detail": c.detail,
                            "remediation": c.remediation,
                        }
                        for c in s.checks
                    ],
                }
                for name, s in self.nodes.items()
            },
        }


TcpProbe = Callable[[str, int, float], tuple[bool, str]]
SerialScanner = Callable[[], list[str]]
WhichFn = Callable[[str], str | None]
MqttMeshRoundTripFn = Callable[[HilQaConfig], tuple[bool, str]]


def default_tcp_probe(host: str, port: int, timeout: float) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"TCP {host}:{port} acessível"
    except OSError as exc:
        return False, f"TCP {host}:{port} inacessível ({exc})"


def default_serial_scanner() -> list[str]:
    dev_dir = Path("/dev")
    if not dev_dir.is_dir():
        return []
    found = sorted(
        str(p)
        for p in (*dev_dir.glob("ttyACM*"), *dev_dir.glob("ttyUSB*"))
    )
    return found


def _parse_host_port(url: str, default_host: str, default_port: int) -> tuple[str, int]:
    parsed = urlparse(url)
    host = parsed.hostname or default_host
    port = parsed.port or default_port
    return host, port


def _check_redis_resp(host: str, port: int, timeout: float) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(b"*1\r\n$4\r\nPING\r\n")
            reply = sock.recv(64).decode("utf-8", errors="replace").strip()
            if "PONG" in reply:
                return True, f"Redis PING -> {reply}"
            return False, f"Resposta inesperada do Redis: {reply!r}"
    except OSError as exc:
        return False, f"Redis inacessível em {host}:{port} ({exc})"


def _check_pgvector(
    pg_dsn: str,
    *,
    tcp_probe: TcpProbe,
    timeout: float,
    sync_runner: Runner = default_runner,
    which_fn: WhichFn = shutil.which,
) -> CheckResult:
    if not pg_dsn:
        ok, detail = tcp_probe("127.0.0.1", 5432, timeout)
        if not ok:
            return CheckResult(
                node="PC Hub",
                check="postgres_pgvector",
                ok=False,
                detail=detail,
                remediation="Subir PostgreSQL com pgvector e configurar YBY_PGVECTOR_DSN no .env",
            )
        return CheckResult(
            node="PC Hub",
            check="postgres_pgvector",
            ok=False,
            detail="Porta 5432 aberta, mas YBY_PGVECTOR_DSN/YBY_DATABASE_URL está vazio",
            remediation="Definir YBY_PGVECTOR_DSN com extensão vector habilitada no .env",
        )

    host, port = _parse_host_port(pg_dsn, "127.0.0.1", 5432)
    ok, detail = tcp_probe(host, port, timeout)
    if not ok:
        return CheckResult(
            node="PC Hub",
            check="postgres_pgvector",
            ok=False,
            detail=detail,
            remediation="Iniciar PostgreSQL e confirmar acesso na porta configurada",
        )

    try:
        import psycopg  # type: ignore[import-not-found]

        with psycopg.connect(pg_dsn, connect_timeout=max(1, int(timeout))) as conn:
            row = conn.execute(
                "SELECT extname FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()
            if row is None:
                return CheckResult(
                    node="PC Hub",
                    check="postgres_pgvector",
                    ok=False,
                    detail="PostgreSQL conectado, mas extensão pgvector ausente",
                    remediation="Executar CREATE EXTENSION IF NOT EXISTS vector; no banco do YBY",
                )
            return CheckResult(
                node="PC Hub",
                check="postgres_pgvector",
                ok=True,
                detail="PostgreSQL + extensão pgvector ativos",
            )
    except ImportError:
        if which_fn("psql"):
            res = sync_runner(
                [
                    "psql",
                    pg_dsn,
                    "-tAc",
                    "SELECT extname FROM pg_extension WHERE extname = 'vector'",
                ],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0 and "vector" in res.stdout:
                return CheckResult(
                    node="PC Hub",
                    check="postgres_pgvector",
                    ok=True,
                    detail="PostgreSQL + extensão pgvector ativos (via psql)",
                )
            return CheckResult(
                node="PC Hub",
                check="postgres_pgvector",
                ok=False,
                detail=f"psql não confirmou extensão vector (exit={res.returncode})",
                remediation="Habilitar extensão vector e validar YBY_PGVECTOR_DSN",
            )
        return CheckResult(
            node="PC Hub",
            check="postgres_pgvector",
            ok=False,
            detail=f"{detail}, mas psycopg e psql estão ausentes para validar pgvector",
            remediation="Instalar psycopg[binary] (pip install 'psycopg[binary]') ou postgresql-client",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            node="PC Hub",
            check="postgres_pgvector",
            ok=False,
            detail=f"Falha ao autenticar/consultar PostgreSQL: {exc}",
            remediation="Verificar credenciais e extensão pgvector em YBY_PGVECTOR_DSN",
        )


async def _http_get_ok(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[bool, int, str]:
    try:
        resp = await client.get(url, headers=headers)
        return resp.status_code == 200, resp.status_code, resp.text[:160]
    except Exception as exc:  # noqa: BLE001
        return False, 0, str(exc)


class _QaLocalLLM:
    """Backend determinístico offline para validar PrivacyGate e failover no CognitiveRouter."""

    def __init__(self, *, fail_tiers: set[RouteTier] | None = None) -> None:
        self.fail_tiers = fail_tiers or set()
        self.calls: list[RouteTier] = []

    async def complete(
        self,
        tier: RouteTier,
        prompt: str,
        *,
        system: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> tuple[str, str]:
        del system, metadata
        self.calls.append(tier)
        if tier in self.fail_tiers:
            raise RuntimeError(f"Tier {tier} indisponível para teste de failover")
        return f"QA OK ({tier}): {prompt[:40]}", f"qa-{tier}"


def default_mqtt_mesh_roundtrip(cfg: HilQaConfig) -> tuple[bool, str]:
    """Valida publicação/recebimento real QoS 1 no Mosquitto para áudio + T-Watch."""

    import paho.mqtt.client as mqtt

    received: list[tuple[str, str]] = []
    ready = threading.Event()
    done = threading.Event()
    client_id = f"yby-hil-qa-sub-{uuid.uuid4().hex[:8]}"

    if hasattr(mqtt, "CallbackAPIVersion"):
        sub = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
    else:
        sub = mqtt.Client(client_id=client_id)

    def on_connect(client: Any, _ud: Any, _flags: Any, rc: Any, _props: Any = None) -> None:
        if rc == 0:
            client.subscribe(TOPIC_AUDIO_STATE, qos=1)
            client.subscribe(TOPIC_TWATCH_CMD, qos=1)
            client.subscribe(TOPIC_TWATCH_TELEMETRY, qos=1)
            ready.set()

    def on_message(_client: Any, _ud: Any, msg: Any) -> None:
        payload = msg.payload.decode("utf-8", errors="replace")
        received.append((msg.topic, payload))
        topics_seen = {t for t, _ in received}
        if TOPIC_AUDIO_STATE in topics_seen and TOPIC_TWATCH_CMD in topics_seen:
            done.set()

    sub.on_connect = on_connect
    sub.on_message = on_message
    if cfg.mqtt_user:
        sub.username_pw_set(cfg.mqtt_user, cfg.mqtt_pass)

    pub = PahoMqttPublisher(
        host=cfg.mqtt_host,
        port=cfg.mqtt_port,
        client_id=f"yby-hil-qa-pub-{uuid.uuid4().hex[:8]}",
        username=cfg.mqtt_user,
        password=cfg.mqtt_pass,
    )
    try:
        sub.connect(cfg.mqtt_host, cfg.mqtt_port, keepalive=30)
        sub.loop_start()
        if not ready.wait(timeout=cfg.timeout_seconds):
            return False, f"Timeout conectando subscriber MQTT em {cfg.mqtt_host}:{cfg.mqtt_port}"

        async def _drive(publisher: MqttPublisher) -> None:
            for st in ("listening", "thinking", "speaking", "idle"):
                ev = AudioStateEvent(state=st, detail="hil-qa")  # type: ignore[arg-type]
                await publisher.publish(
                    TOPIC_AUDIO_STATE,
                    ev.model_dump_json(),
                    qos=1,
                    retain=False,
                )

            qa_router = CognitiveRouter(backend=_QaLocalLLM())
            bridge = TWatchBridge(router=qa_router, mqtt_bus=publisher)
            voice_env = TWatchVoiceEnvelope(
                device_id="twatch-s3-plus-01",
                transcript="Status da malha",
                audio_b64=None,
                sensitivity="private",
            )
            await bridge.handle_voice_message(voice_env.model_dump_json())
            await bridge.emit_machine_alert("hil-qa", "Validação ponta a ponta Módulo C")

        asyncio.run(_drive(pub))
        if not done.wait(timeout=cfg.timeout_seconds):
            return False, f"Mensagens MQTT não retornaram no broker (recebidas={len(received)})"

        cmds = [
            TWatchCommand.model_validate_json(payload)
            for topic, payload in received
            if topic == TOPIC_TWATCH_CMD
        ]
        if not any(c.command == "display_text" for c in cmds) or not any(
            c.command == "haptic_pulse" for c in cmds
        ):
            return False, "Tópicos T-Watch não entregaram display_text + haptic_pulse"

        telemetry_count = sum(1 for topic, _ in received if topic == TOPIC_TWATCH_TELEMETRY)
        return (
            True,
            f"MQTT QoS 1 OK ({len(received)} msgs; telemetria T-Watch observada={telemetry_count})",
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"Falha no barramento MQTT ({cfg.mqtt_host}:{cfg.mqtt_port}): {exc}"
    finally:
        pub.close()
        sub.loop_stop()
        sub.disconnect()


async def _diagnose_pc_hub(
    cfg: HilQaConfig,
    *,
    client: httpx.AsyncClient,
    tcp_probe: TcpProbe,
    redis_probe: Callable[[str, int, float], tuple[bool, str]],
    sync_runner: Runner = default_runner,
    which_fn: WhichFn = shutil.which,
    pg_probe: Callable[[HilQaConfig], CheckResult] | None = None,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    checks.append(
        pg_probe(cfg)
        if pg_probe is not None
        else _check_pgvector(
            cfg.pg_dsn,
            tcp_probe=tcp_probe,
            timeout=cfg.timeout_seconds,
            sync_runner=sync_runner,
            which_fn=which_fn,
        )
    )

    r_host, r_port = _parse_host_port(cfg.redis_url, "127.0.0.1", 6379)
    r_ok, r_detail = redis_probe(r_host, r_port, cfg.timeout_seconds)
    checks.append(
        CheckResult(
            node="PC Hub",
            check="redis",
            ok=r_ok,
            detail=r_detail,
            remediation="" if r_ok else f"Iniciar Redis em {r_host}:{r_port}",
        )
    )

    m_ok, m_detail = tcp_probe(cfg.mqtt_host, cfg.mqtt_port, cfg.timeout_seconds)
    checks.append(
        CheckResult(
            node="PC Hub",
            check="mosquitto",
            ok=m_ok,
            detail=m_detail,
            remediation="" if m_ok else f"Iniciar Eclipse Mosquitto em {cfg.mqtt_host}:{cfg.mqtt_port}",
        )
    )

    o_ok, o_code, o_body = await _http_get_ok(client, f"{cfg.ollama_base_url}/api/tags")
    checks.append(
        CheckResult(
            node="PC Hub",
            check="ollama",
            ok=o_ok,
            detail=f"Ollama HTTP {o_code}" if o_ok else f"Ollama falhou ({o_code}: {o_body})",
            remediation="" if o_ok else f"Subir Ollama em {cfg.ollama_base_url}",
        )
    )

    litellm_headers = (
        {"Authorization": f"Bearer {cfg.litellm_master_key}"}
        if cfg.litellm_master_key
        else None
    )
    l_ok, l_code, l_body = await _http_get_ok(
        client,
        f"{cfg.litellm_base_url}/health/liveliness",
        headers=litellm_headers,
    )
    if not l_ok:
        l_ok, l_code, l_body = await _http_get_ok(
            client,
            f"{cfg.litellm_base_url}/health",
            headers=litellm_headers,
        )
    checks.append(
        CheckResult(
            node="PC Hub",
            check="litellm",
            ok=l_ok,
            detail=f"LiteLLM HTTP {l_code}" if l_ok else f"LiteLLM falhou ({l_code}: {l_body})",
            remediation=""
            if l_ok
            else f"Subir proxy LiteLLM com litellm_config.yaml em {cfg.litellm_base_url}",
        )
    )

    f_ok, f_code, f_body = await _http_get_ok(client, f"{cfg.mesh_base_url}/health")
    checks.append(
        CheckResult(
            node="PC Hub",
            check="fastapi_mesh",
            ok=f_ok,
            detail=f"FastAPI Mesh HTTP {f_code}" if f_ok else f"FastAPI Mesh falhou ({f_code}: {f_body})",
            remediation="" if f_ok else f"Iniciar FastAPI Mesh (src/yby/app.py) em {cfg.mesh_base_url}",
        )
    )

    ym_ok, ym_code, ym_body = await _http_get_ok(client, f"{cfg.machine_base_url}/health")
    schema_ok, schema_code, _ = await _http_get_ok(
        client,
        f"{cfg.machine_base_url}/api/machine/schema",
    )
    both_ym = ym_ok and schema_ok
    checks.append(
        CheckResult(
            node="PC Hub",
            check="yby_machine",
            ok=both_ym,
            detail=(
                f"yby_machine /health={ym_code}, /schema={schema_code}"
                if both_ym
                else f"yby_machine indisponível ({ym_code}/{schema_code}: {ym_body})"
            ),
            remediation=""
            if both_ym
            else f"Iniciar yby_machine (src/yby_machine/http.py) em {cfg.machine_base_url}",
        )
    )
    return checks


async def _diagnose_baseus(
    cfg: HilQaConfig,
    *,
    async_runner: CommandRunner,
    sync_runner: Runner,
    which_fn: WhichFn,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    missing_bins = [b for b in ("pactl", "pw-record", "pw-play") if not which_fn(b)]
    if missing_bins:
        checks.append(
            CheckResult(
                node="Baseus Bowie MC2 Air",
                check="pipewire_bins",
                ok=False,
                detail=f"Binários ausentes: {', '.join(missing_bins)}",
                remediation=f"Instalar pacotes PipeWire/PulseAudio ({', '.join(missing_bins)})",
            )
        )
        return checks

    device = PipeWireBluetoothDevice(
        device_name=cfg.bt_device_name,
        runner=async_runner,
    )
    card = await device.detect_device()
    checks.append(
        CheckResult(
            node="Baseus Bowie MC2 Air",
            check="pipewire_card",
            ok=card is not None,
            detail=f"Card PipeWire detectado: {card}" if card else f"Card '{cfg.bt_device_name}' não encontrado no pactl",
            remediation=""
            if card
            else f"Parear e conectar '{cfg.bt_device_name}' via Bluetooth (bluetoothctl) no PC Hub",
        )
    )

    if which_fn("bluetoothctl"):
        bt_res = sync_runner(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True)
        connected_match = (
            bt_res.returncode == 0
            and ("baseus" in bt_res.stdout.casefold() or "bowie" in bt_res.stdout.casefold())
        )
        checks.append(
            CheckResult(
                node="Baseus Bowie MC2 Air",
                check="bluetooth_link",
                ok=connected_match,
                detail="Bluetooth Connected confirmado" if connected_match else "Fone não listado em bluetoothctl Connected",
                remediation="" if connected_match else "Conectar Baseus Bowie MC2 Air via bluetoothctl connect <MAC>",
            )
        )
    return checks


async def _diagnose_xiaomi12(
    cfg: HilQaConfig,
    *,
    client: httpx.AsyncClient,
    sync_runner: Runner,
    which_fn: WhichFn,
    tcp_probe: TcpProbe,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    pp_host, pp_port = _parse_host_port(cfg.pocketpal_base_url, "100.64.0.2", 8080)

    if which_fn("tailscale"):
        ts_res = sync_runner(["tailscale", "status", "--json"], capture_output=True, text=True)
        ts_ok = False
        ts_detail = "Tailscale não conectado"
        if ts_res.returncode == 0 and ts_res.stdout.strip():
            try:
                data = json.loads(ts_res.stdout)
                backend = str(data.get("BackendState", ""))
                peers = data.get("Peer", {}) or {}
                peer_ips = [
                    str(ip)
                    for peer in peers.values()
                    for ip in (peer.get("TailscaleIPs") or [])
                ]
                has_peer = pp_host in peer_ips or any(
                    "xiaomi" in str(p.get("HostName", "")).casefold()
                    for p in peers.values()
                )
                ts_ok = backend == "Running" and (has_peer or tcp_probe(pp_host, pp_port, cfg.timeout_seconds)[0])
                ts_detail = f"Tailscale={backend}, peer_xiaomi={has_peer}"
            except json.JSONDecodeError:
                ts_detail = "Saída JSON inválida de tailscale status"
        checks.append(
            CheckResult(
                node="Xiaomi 12",
                check="tailscale",
                ok=ts_ok,
                detail=ts_detail,
                remediation=""
                if ts_ok
                else f"Conectar Tailscale no PC Hub e Xiaomi 12 ({pp_host})",
            )
        )
    else:
        lan_ok, lan_detail = tcp_probe(pp_host, pp_port, cfg.timeout_seconds)
        checks.append(
            CheckResult(
                node="Xiaomi 12",
                check="tailscale_or_lan",
                ok=lan_ok,
                detail=f"CLI tailscale ausente; {lan_detail}",
                remediation=""
                if lan_ok
                else f"Instalar/conectar Tailscale ou verificar LAN até {pp_host}:{pp_port}",
            )
        )

    pp_ok, pp_code, pp_body = await _http_get_ok(client, f"{cfg.pocketpal_base_url}/models")
    checks.append(
        CheckResult(
            node="Xiaomi 12",
            check="pocketpal_ai",
            ok=pp_ok,
            detail=f"PocketPal /v1/models HTTP {pp_code}" if pp_ok else f"PocketPal inacessível ({pp_code}: {pp_body})",
            remediation=""
            if pp_ok
            else f"Abrir PocketPal AI Local Server na porta {pp_port} do Xiaomi 12",
        )
    )

    edge_h_ok, eh_code, eh_body = await _http_get_ok(client, f"{cfg.mesh_base_url}/edge/health")
    edge_headers = (
        {"Authorization": f"Bearer {cfg.edge_sync_token}"}
        if cfg.edge_sync_token
        else None
    )
    edge_s_ok, es_code, es_body = await _http_get_ok(
        client,
        f"{cfg.mesh_base_url}/edge/sync/status",
        headers=edge_headers,
    )
    edge_ok = edge_h_ok and edge_s_ok
    remediation = ""
    if not edge_ok:
        if not cfg.edge_sync_token:
            remediation = "Definir YBY_EDGE_SYNC_TOKEN/GATEWAY_TOKEN no .env e subir /edge/sync"
        else:
            remediation = f"Subir router /edge/sync em {cfg.mesh_base_url} e validar token"
    checks.append(
        CheckResult(
            node="Xiaomi 12",
            check="edge_sync",
            ok=edge_ok,
            detail=(
                f"/edge/health={eh_code}, /edge/sync/status={es_code}"
                if edge_ok
                else f"/edge-sync falhou ({eh_code}/{es_code}: {eh_body or es_body})"
            ),
            remediation=remediation,
        )
    )
    return checks


def _diagnose_and_backup_twatch(
    cfg: HilQaConfig,
    *,
    serial_scanner: SerialScanner,
    sync_runner: Runner,
    which_fn: WhichFn,
    skip_backup_hw: bool,
) -> tuple[list[CheckResult], str | None, str | None]:
    checks: list[CheckResult] = []
    ports = [cfg.twatch_port] if cfg.twatch_port else serial_scanner()
    detected_port = ports[0] if ports else None

    checks.append(
        CheckResult(
            node="LILYGO T-Watch S3 Plus",
            check="usb_serial",
            ok=detected_port is not None,
            detail=f"Porta serial USB detectada: {detected_port}" if detected_port else "Nenhuma porta /dev/ttyACM* ou /dev/ttyUSB* detectada",
            remediation=""
            if detected_port
            else "Conectar LILYGO T-Watch S3 Plus na USB (ou definir YBY_TWATCH_PORT)",
        )
    )

    has_esptool = bool(which_fn("esptool.py") or which_fn("esptool"))
    if not has_esptool:
        probe = sync_runner([sys.executable, "-m", "esptool", "version"], capture_output=True, text=True)
        has_esptool = probe.returncode == 0
    checks.append(
        CheckResult(
            node="LILYGO T-Watch S3 Plus",
            check="esptool",
            ok=has_esptool,
            detail="esptool disponível" if has_esptool else "esptool.py não instalado",
            remediation="" if has_esptool else "Instalar esptool (pip install esptool) no ambiente do PC Hub",
        )
    )

    backup_bin_str: str | None = None
    backup_sha_str: str | None = None

    if skip_backup_hw:
        checks.append(
            CheckResult(
                node="LILYGO T-Watch S3 Plus",
                check="flash_backup_16mb",
                ok=True,
                detail="Backup físico ignorado (--skip-backup-hw)",
            )
        )
        return checks, None, None

    if not detected_port or not has_esptool:
        checks.append(
            CheckResult(
                node="LILYGO T-Watch S3 Plus",
                check="flash_backup_16mb",
                ok=False,
                detail="Backup de 16 MB bloqueado (porta USB ou esptool ausente)",
                remediation="Com o relógio na USB e esptool instalado, rodar make twatch-backup",
            )
        )
        return checks, None, None

    try:
        bin_path, sha_path = run_backup(
            backup_dir=cfg.twatch_backup_dir,
            port=detected_port,
            runner=sync_runner,
        )
        verified = verify_backup_sha256(bin_path, sha_path)
        backup_bin_str = str(bin_path)
        backup_sha_str = sha_path.read_text(encoding="utf-8").strip().split()[0]
        checks.append(
            CheckResult(
                node="LILYGO T-Watch S3 Plus",
                check="flash_backup_16mb",
                ok=verified,
                detail=f"Dump 16 MB verificado ({bin_path.name}, sha256={backup_sha_str[:12]}...)"
                if verified
                else "Falha na verificação SHA-256 do backup",
                remediation="" if verified else "Refazer make twatch-backup com cabo USB estável",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            CheckResult(
                node="LILYGO T-Watch S3 Plus",
                check="flash_backup_16mb",
                ok=False,
                detail=f"Erro no backup 16 MB: {exc}",
                remediation="Colocar ESP32-S3 em modo bootloader se necessário e rodar make twatch-backup",
            )
        )
    return checks, backup_bin_str, backup_sha_str


async def _run_e2e_mesh_checks(
    cfg: HilQaConfig,
    *,
    client: httpx.AsyncClient,
    mqtt_roundtrip_fn: MqttMeshRoundTripFn,
) -> list[CheckResult]:
    checks: list[CheckResult] = []

    # 1) Privacy Gate (D12): payload privado NUNCA escala para nuvem
    gate = PrivacyGate()
    private_req = RouteRequest(
        prompt="Resumo privado do meu dia",
        sensitivity="private",
        origin="user_prompt",
        source_node="hil-qa",
    )
    decision = gate.evaluate(private_req)
    router_cfg = RouterConfig(
        ollama_base_url=f"{cfg.ollama_base_url}/v1",
        pocketpal_base_url=cfg.pocketpal_base_url,
        pocketpal_model=cfg.pocketpal_model,
        request_timeout_seconds=cfg.timeout_seconds,
    )
    private_router = CognitiveRouter(config=router_cfg, backend=_QaLocalLLM())
    priv_resp = await private_router.route(private_req)
    privacy_ok = (not decision.allow_cloud) and priv_resp.metadata.privacy_blocked_cloud
    checks.append(
        CheckResult(
            node="PC Hub",
            check="e2e_privacy_gate",
            ok=privacy_ok,
            detail="PrivacyGate bloqueou nuvem (D12 fail-closed)" if privacy_ok else "PrivacyGate falhou em bloquear nuvem",
            remediation="" if privacy_ok else "Revisar src/yby/routing/privacy_gate.py",
        )
    )

    # 2) Failover para Xiaomi 12 (NodeHealthTracker + PocketPal vivo quando acessível)
    qa_cache = InMemoryCacheBackend()
    tracker = NodeHealthTracker(qa_cache, unhealthy_ttl_seconds=60)
    await tracker.mark_unhealthy(PC_HUB_NODE, "hil-qa-failover-test")
    failover_router = CognitiveRouter(
        config=router_cfg,
        backend=_QaLocalLLM(),
        cache=qa_cache,
        health=tracker,
    )
    failover_resp = await failover_router.route(private_req)
    router_failover_ok = failover_resp.tier == "yby-mobile-fallback"

    pocketpal_chat_ok = False
    pocketpal_detail = ""
    try:
        resp = await client.post(
            f"{cfg.pocketpal_base_url}/chat/completions",
            json={
                "model": cfg.pocketpal_model,
                "messages": [{"role": "user", "content": "Responda apenas OK"}],
                "max_tokens": 8,
                "temperature": 0.0,
            },
        )
        pocketpal_chat_ok = resp.status_code == 200
        pocketpal_detail = f"PocketPal chat HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        pocketpal_detail = f"PocketPal chat indisponível ({exc})"

    checks.append(
        CheckResult(
            node="Xiaomi 12",
            check="e2e_failover_pocketpal",
            ok=router_failover_ok and pocketpal_chat_ok,
            detail=f"CognitiveRouter->yby-mobile-fallback={router_failover_ok}; {pocketpal_detail}",
            remediation=""
            if (router_failover_ok and pocketpal_chat_ok)
            else "Garantir PocketPal AI ativo com modelo carregado no Xiaomi 12 via Tailscale",
        )
    )

    # 3) Fluxo MQTT ponta a ponta: yby/audio/state + TWatchBridge 2C + yby_machine -> T-Watch cmd
    mqtt_ok, mqtt_detail = await asyncio.to_thread(mqtt_roundtrip_fn, cfg)
    checks.append(
        CheckResult(
            node="LILYGO T-Watch S3 Plus",
            check="e2e_mqtt_mesh",
            ok=mqtt_ok,
            detail=mqtt_detail,
            remediation=""
            if mqtt_ok
            else f"Verificar Mosquitto em {cfg.mqtt_host}:{cfg.mqtt_port} e assinatura do T-Watch",
        )
    )
    return checks


def _build_report(
    checks: Sequence[CheckResult],
    *,
    backup_bin: str | None = None,
    backup_sha256: str | None = None,
) -> HilQaReport:
    nodes: dict[str, NodeSummary] = {
        name: NodeSummary(node=name, status="OK") for name in OFFICIAL_NODES
    }
    for item in checks:
        summary = nodes[item.node]
        summary.checks.append(item)
        if not item.ok:
            summary.status = "PENDENTE"
            if item.remediation and item.remediation not in summary.remediations:
                summary.remediations.append(item.remediation)
    return HilQaReport(nodes=nodes, backup_bin=backup_bin, backup_sha256=backup_sha256)


async def run_hil_qa_async(
    cfg: HilQaConfig,
    *,
    http_client: httpx.AsyncClient | None = None,
    tcp_probe: TcpProbe = default_tcp_probe,
    redis_probe: Callable[[str, int, float], tuple[bool, str]] = _check_redis_resp,
    pg_probe: Callable[[HilQaConfig], CheckResult] | None = None,
    async_runner: CommandRunner | None = None,
    sync_runner: Runner = default_runner,
    which_fn: WhichFn = shutil.which,
    serial_scanner: SerialScanner = default_serial_scanner,
    mqtt_roundtrip_fn: MqttMeshRoundTripFn = default_mqtt_mesh_roundtrip,
    skip_backup_hw: bool = False,
) -> HilQaReport:
    """Executa as 4 etapas da validação HIL e retorna o relatório consolidado."""

    runner_async = async_runner or SubprocessCommandRunner()
    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=cfg.timeout_seconds)

    try:
        hub_checks = await _diagnose_pc_hub(
            cfg,
            client=client,
            tcp_probe=tcp_probe,
            redis_probe=redis_probe,
            sync_runner=sync_runner,
            which_fn=which_fn,
            pg_probe=pg_probe,
        )
        baseus_checks = await _diagnose_baseus(
            cfg,
            async_runner=runner_async,
            sync_runner=sync_runner,
            which_fn=which_fn,
        )
        xiaomi_checks = await _diagnose_xiaomi12(
            cfg,
            client=client,
            sync_runner=sync_runner,
            which_fn=which_fn,
            tcp_probe=tcp_probe,
        )
        twatch_checks, backup_bin, backup_sha = _diagnose_and_backup_twatch(
            cfg,
            serial_scanner=serial_scanner,
            sync_runner=sync_runner,
            which_fn=which_fn,
            skip_backup_hw=skip_backup_hw,
        )
        e2e_checks = await _run_e2e_mesh_checks(
            cfg,
            client=client,
            mqtt_roundtrip_fn=mqtt_roundtrip_fn,
        )
    finally:
        if owns_client:
            await client.aclose()

    all_checks = [
        *hub_checks,
        *baseus_checks,
        *xiaomi_checks,
        *twatch_checks,
        *e2e_checks,
    ]
    return _build_report(all_checks, backup_bin=backup_bin, backup_sha256=backup_sha)


def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=False)

    parser = argparse.ArgumentParser(
        description="QA Hardware-in-the-Loop (HIL) da malha YBY de 4 nós",
    )
    parser.add_argument("--json", action="store_true", help="Emite relatório detalhado em JSON")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mostra detalhes de cada subchecagem além da tabela final",
    )
    parser.add_argument(
        "--skip-backup-hw",
        action="store_true",
        help="Ignora o dump físico de 16 MB da flash (apenas dry-run sem relógio USB)",
    )
    parser.add_argument(
        "--allow-pending",
        action="store_true",
        help="Retorna exit code 0 mesmo quando algum nó estiver PENDENTE",
    )
    args = parser.parse_args(argv)

    cfg = HilQaConfig.from_env()
    report = asyncio.run(run_hil_qa_async(cfg, skip_backup_hw=args.skip_backup_hw))

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        if args.verbose:
            for node_name in OFFICIAL_NODES:
                for chk in report.nodes[node_name].checks:
                    tag = "OK" if chk.ok else "PENDENTE"
                    print(f"[{tag}] {chk.node} :: {chk.check} -> {chk.detail}")
            print()
        print(report.to_markdown_table())

    if report.all_ok or args.allow_pending:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
