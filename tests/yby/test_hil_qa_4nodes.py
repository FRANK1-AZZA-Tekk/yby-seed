"""Testes 100% offline do orquestrador HIL QA dos 4 nós (scripts/hil_qa_4nodes.py)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import httpx
import pytest

from scripts.hil_qa_4nodes import (
    OFFICIAL_NODES,
    CheckResult,
    HilQaConfig,
    run_hil_qa_async,
)


class _FakeAsyncCommandRunner:
    def __init__(self, *, pactl_out: bytes) -> None:
        self._pactl_out = pactl_out

    async def run(
        self,
        argv: list[str] | tuple[str, ...],
        *,
        stdin_bytes: bytes | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, bytes, bytes]:
        del stdin_bytes, timeout
        if "pactl" in argv[0] and "cards" in argv:
            return 0, self._pactl_out, b""
        return 1, b"", b"unsupported"


def _make_mock_http_client(*, pocketpal_ok: bool = True, mesh_ok: bool = True) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith(":11434/api/tags"):
            return httpx.Response(200, json={"models": []})
        if url.endswith(":4000/health/liveliness"):
            return httpx.Response(200, json={"status": "alive"})
        if url.endswith(":8000/health"):
            return httpx.Response(200 if mesh_ok else 503, json={"status": "ok"})
        if url.endswith(":8000/edge/health"):
            return httpx.Response(200 if mesh_ok else 503, json={"status": "ok"})
        if url.endswith(":8000/edge/sync/status"):
            auth = request.headers.get("Authorization", "")
            if auth != "Bearer tok-hil":
                return httpx.Response(401, json={"detail": "unauthorized"})
            return httpx.Response(200, json={"pending": 0})
        if url.endswith(":8001/health"):
            return httpx.Response(200, json={"status": "ok"})
        if url.endswith(":8001/api/machine/schema"):
            return httpx.Response(200, json={"title": "YBYSpec"})
        if url.endswith(":8080/v1/models"):
            return httpx.Response(200 if pocketpal_ok else 503, json={"data": []})
        if url.endswith(":8080/v1/chat/completions"):
            return httpx.Response(
                200 if pocketpal_ok else 503,
                json={"choices": [{"message": {"content": "OK"}}]},
            )
        return httpx.Response(404, json={"detail": f"unexpected {url}"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_hil_qa_config_defaults_and_env_overrides() -> None:
    default_cfg = HilQaConfig.from_env({})
    assert default_cfg.litellm_base_url == "http://127.0.0.1:4000"
    assert default_cfg.mesh_base_url == "http://127.0.0.1:8000"
    assert default_cfg.machine_base_url == "http://127.0.0.1:8001"
    assert default_cfg.mqtt_port == 1883
    assert default_cfg.pocketpal_base_url == "http://100.64.0.2:8080/v1"

    custom_cfg = HilQaConfig.from_env(
        {
            "YBY_LITELLM_BASE_URL": "http://127.0.0.1:4100/",
            "YBY_MESH_BASE_URL": "http://127.0.0.1:8100/",
            "YBY_MACHINE_BASE_URL": "http://127.0.0.1:8101/",
            "YBY_MQTT_PORT": "1884",
            "YBY_EDGE_SYNC_TOKEN": "sec",
            "YBY_TWATCH_PORT": "/dev/ttyACM9",
        }
    )
    assert custom_cfg.litellm_base_url == "http://127.0.0.1:4100"
    assert custom_cfg.mesh_base_url == "http://127.0.0.1:8100"
    assert custom_cfg.machine_base_url == "http://127.0.0.1:8101"
    assert custom_cfg.mqtt_port == 1884
    assert custom_cfg.edge_sync_token == "sec"
    assert custom_cfg.twatch_port == "/dev/ttyACM9"


@pytest.mark.asyncio
async def test_hil_qa_all_4_nodes_ok_with_16mb_sha256_backup(tmp_path: Path) -> None:
    cfg = HilQaConfig(
        pg_dsn="postgresql://yby:yby@127.0.0.1:5432/yby",
        edge_sync_token="tok-hil",
        twatch_backup_dir=tmp_path,
    )

    def fake_sync_runner(cmd: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        if cmd[0] == "bluetoothctl":
            return subprocess.CompletedProcess(
                cmd,
                0,
                "Device AA:BB:CC:DD:EE:FF Baseus Bowie MC2 Air\n",
                "",
            )
        if cmd[0] == "tailscale":
            payload = {
                "BackendState": "Running",
                "Peer": {
                    "p1": {
                        "HostName": "xiaomi12",
                        "TailscaleIPs": ["100.64.0.2"],
                    }
                },
            }
            return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")
        if "read_flash" in cmd:
            Path(cmd[-1]).write_bytes(b"\xE9TWATCH_16MB_DUMP")
            return subprocess.CompletedProcess(cmd, 0, "ok", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    async with _make_mock_http_client() as client:
        report = await run_hil_qa_async(
            cfg,
            http_client=client,
            tcp_probe=lambda h, p, _t: (True, f"TCP {h}:{p} OK"),
            redis_probe=lambda _h, _p, _t: (True, "Redis PING -> +PONG"),
            pg_probe=lambda _c: CheckResult(
                node="PC Hub",
                check="postgres_pgvector",
                ok=True,
                detail="PostgreSQL + pgvector OK",
            ),
            async_runner=_FakeAsyncCommandRunner(
                pactl_out=b"42\tbluez_card.AA_BB_CC_DD_EE_FF_baseus_bowie_mc2_air\tmodule-bluez5-device.c\n"
            ),
            sync_runner=fake_sync_runner,
            which_fn=lambda name: f"/usr/bin/{name}",
            serial_scanner=lambda: ["/dev/ttyACM0"],
            mqtt_roundtrip_fn=lambda _c: (True, "MQTT QoS 1 OK (6 msgs)"),
        )

    assert report.all_ok is True
    assert report.backup_bin is not None
    assert report.backup_sha256 is not None
    bin_path = Path(report.backup_bin)
    sha_path = Path(f"{bin_path}.sha256")
    assert bin_path.is_file()
    assert sha_path.is_file()
    assert hashlib.sha256(bin_path.read_bytes()).hexdigest() == report.backup_sha256

    table = report.to_markdown_table()
    lines = table.splitlines()
    assert len(lines) == 6  # cabeçalho + separador + 4 nós oficiais
    for node_name in OFFICIAL_NODES:
        assert f"| {node_name} | OK | - |" in table


@pytest.mark.asyncio
async def test_hil_qa_reports_pendente_and_remediations_when_nodes_missing(tmp_path: Path) -> None:
    cfg = HilQaConfig(
        pg_dsn="",
        edge_sync_token="",
        twatch_backup_dir=tmp_path,
    )

    def failing_sync_runner(cmd: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, "", "not connected")

    async with _make_mock_http_client(pocketpal_ok=False, mesh_ok=False) as client:
        report = await run_hil_qa_async(
            cfg,
            http_client=client,
            tcp_probe=lambda h, p, _t: (False, f"TCP {h}:{p} down"),
            redis_probe=lambda _h, _p, _t: (False, "Redis down"),
            async_runner=_FakeAsyncCommandRunner(pactl_out=b""),
            sync_runner=failing_sync_runner,
            which_fn=lambda name: None if name in {"esptool.py", "esptool", "tailscale"} else f"/usr/bin/{name}",
            serial_scanner=list,
            mqtt_roundtrip_fn=lambda _c: (False, "Mosquitto offline"),
        )

    assert report.all_ok is False
    assert report.backup_bin is None
    for node_name in OFFICIAL_NODES:
        summary = report.nodes[node_name]
        assert summary.status == "PENDENTE"
        assert len(summary.remediations) >= 1

    table = report.to_markdown_table()
    assert "| PC Hub | PENDENTE |" in table
    assert "| Baseus Bowie MC2 Air | PENDENTE |" in table
    assert "| Xiaomi 12 | PENDENTE |" in table
    assert "| LILYGO T-Watch S3 Plus | PENDENTE |" in table

    payload = report.to_dict()
    assert payload["all_ok"] is False
    assert set(payload["nodes"].keys()) == set(OFFICIAL_NODES)


def test_hil_qa_redis_resp_socket_and_psql_pgvector_fallback() -> None:
    import socket
    import threading

    from scripts.hil_qa_4nodes import _check_pgvector, _check_redis_resp

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def _serve() -> None:
        conn, _ = srv.accept()
        with conn:
            data = conn.recv(64)
            if b"PING" in data:
                conn.sendall(b"+PONG\r\n")

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    ok, detail = _check_redis_resp("127.0.0.1", port, 2.0)
    t.join(timeout=2.0)
    srv.close()
    assert ok is True
    assert "+PONG" in detail

    pg_fail = _check_pgvector(
        "",
        tcp_probe=lambda h, p, _t: (True, f"TCP {h}:{p} OK"),
        timeout=1.0,
    )
    assert pg_fail.ok is False
    assert "YBY_PGVECTOR_DSN" in pg_fail.remediation

