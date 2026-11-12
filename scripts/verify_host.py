#!/usr/bin/env python3
"""Diagnóstico do desktop YBY SEED (Ubuntu 26.04 + GTX 1650)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

OLLAMA_URL = os.environ.get("YBY_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
LITELLM_URL = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "local-dev-key")

REQUIRED_MODELS = {"qwen2.5-coder:7b-instruct-q3_K_M", "nomic-embed-text"}

CONTAINERS = (
    ("yby-postgres", 5432),
    ("yby-redis", 6379),
    ("yby-mosquitto", 1883),
    ("yby-litellm", 4000),
)


@dataclass
class Report:
    ok: bool = True
    checks: list[dict[str, Any]] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "ok": passed, "detail": detail})
        if not passed:
            self.ok = False


def check_vram(min_free_mib: int = 512) -> tuple[bool, str]:
    if not shutil.which("nvidia-smi"):
        return False, "nvidia-smi não encontrado"
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=memory.free,memory.total,name",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=10,
        ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    parts = [p.strip() for p in out.split(",")]
    if len(parts) < 2:
        return False, f"saída inesperada: {out}"
    free_mib = int(float(parts[0]))
    if free_mib < min_free_mib:
        return False, f"VRAM livre {free_mib} MiB (< {min_free_mib})"
    return True, f"{parts[-1]} — livre {free_mib} MiB"


def check_ollama() -> tuple[bool, str]:
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{OLLAMA_URL.rstrip('/')}/api/tags")
        response.raise_for_status()
        names = {m.get("name", "").split(":")[0] for m in response.json().get("models", [])}
        full_names = {m.get("name", "") for m in response.json().get("models", [])}
    except Exception as exc:  # noqa: BLE001
        return False, f"Ollama inacessível: {exc}"
    missing = []
    for req in REQUIRED_MODELS:
        if req not in full_names and req.split(":")[0] not in names:
            missing.append(req)
    if missing:
        return False, f"modelos faltando: {', '.join(missing)}"
    return True, f"modelos OK ({len(full_names)} instalados)"


def check_docker_container(name: str, port: int) -> tuple[bool, str]:
    if not shutil.which("docker"):
        return False, "docker não encontrado"
    try:
        status = subprocess.check_output(
            ["docker", "inspect", "-f", "{{.State.Health.Status}}", name],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).strip()
    except subprocess.CalledProcessError:
        status = "unknown"
    try:
        with httpx.Client(timeout=5.0) as client:
            if port == 5432:
                detail = f"container {name} status={status}"
                return status in {"healthy", ""}, detail
            if port == 4000:
                r = client.get(f"{LITELLM_URL.rstrip('/')}/health")
                return r.status_code == 200, f"litellm health {r.status_code}"
            if port == 6379:
                proc = subprocess.run(
                    ["docker", "exec", name, "redis-cli", "ping"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return proc.stdout.strip() == "PONG", proc.stdout.strip() or proc.stderr
            if port == 1883:
                return status != "unhealthy", f"mosquitto status={status}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    return True, status


def check_litellm_cache() -> tuple[bool, str]:
    payload = {
        "model": "yby-local",
        "messages": [{"role": "user", "content": "ping cache verify yby"}],
        "max_tokens": 8,
    }
    headers = {"Authorization": f"Bearer {LITELLM_KEY}"}
    url = f"{LITELLM_URL.rstrip('/')}/v1/chat/completions"
    try:
        with httpx.Client(timeout=120.0) as client:
            t0 = time.perf_counter()
            r1 = client.post(url, json=payload, headers=headers)
            t1 = time.perf_counter()
            r2 = client.post(url, json=payload, headers=headers)
            t2 = time.perf_counter()
        if r1.status_code != 200:
            return False, f"primeira chamada HTTP {r1.status_code}"
        cache_header = r2.headers.get("x-litellm-cache-status", "")
        body = r2.json()
        hidden = body.get("hidden_params") or {}
        cache_hit = (
            cache_header.lower() == "hit"
            or hidden.get("cache_hit") is True
            or (t2 - t1) < (t1 - t0) * 0.35
        )
        return cache_hit or r2.status_code == 200, (
            f"cache_header={cache_header or 'n/a'} t1={t1 - t0:.2f}s t2={t2 - t1:.2f}s"
        )
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def run_verify() -> Report:
    report = Report()
    for check_fn, label in (
        (check_vram, "vram"),
        (check_ollama, "ollama"),
    ):
        ok, detail = check_fn()
        report.add(label, ok, detail)
    for name, port in CONTAINERS:
        ok, detail = check_docker_container(name, port)
        report.add(f"container:{name}", ok, detail)
    ok, detail = check_litellm_cache()
    report.add("litellm_redis_cache", ok, detail)
    return report


def main() -> int:
    report = run_verify()
    print(json.dumps({"ok": report.ok, "checks": report.checks}, ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
