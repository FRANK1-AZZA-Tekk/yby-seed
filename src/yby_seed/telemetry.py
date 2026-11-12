"""Coleta de telemetria para o painel SSE (GPU, Docker, orçamento, dataset)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import httpx

from src.yby_seed.config import get_settings

INFRA_CONTAINERS = {
    "postgres": "yby-postgres",
    "redis": "yby-redis",
    "mosquitto": "yby-mosquitto",
    "litellm": "yby-litellm",
}


def _run(cmd: list[str], timeout: float = 4.0) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def read_gpu_stats() -> dict[str, Any]:
    result = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.used,memory.total,temperature.gpu",
            "--format=csv,noheader,nounits",
        ]
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {
            "available": False,
            "name": "GTX 1650 (não detectada)",
            "vram_used_mb": 0,
            "vram_total_mb": 4096,
            "temperature_c": 0,
        }

    parts = [p.strip() for p in result.stdout.strip().split(",")]
    if len(parts) < 4:
        return {
            "available": False,
            "name": "GPU",
            "vram_used_mb": 0,
            "vram_total_mb": 4096,
            "temperature_c": 0,
        }

    name, used, total, temp = parts[0], parts[1], parts[2], parts[3]
    return {
        "available": True,
        "name": name,
        "vram_used_mb": int(float(used)),
        "vram_total_mb": int(float(total)),
        "temperature_c": int(float(temp)),
    }


def read_container_status() -> dict[str, str]:
    status: dict[str, str] = {}
    for key, cname in INFRA_CONTAINERS.items():
        proc = _run(["docker", "inspect", "-f", "{{.State.Status}}", cname])
        if proc.returncode != 0:
            status[key] = "down"
            continue
        raw = (proc.stdout or "").strip().lower()
        status[key] = "up" if raw == "running" else raw or "unknown"
    return status


def count_validated_pairs(path: Path | None = None) -> int:
    settings = get_settings()
    target = path or settings.datasets_path
    if not target.is_file():
        return 0
    count = 0
    with target.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def read_openrouter_spend() -> dict[str, float]:
    settings = get_settings()
    cap = settings.openrouter_monthly_budget_usd
    spent = 0.0

    spend_file = Path(os.environ.get("YBY_SPEND_SNAPSHOT", "data/budget/spend.json"))
    if spend_file.is_file():
        try:
            data = json.loads(spend_file.read_text(encoding="utf-8"))
            spent = float(data.get("openrouter_usd", 0.0))
        except (json.JSONDecodeError, TypeError, ValueError):
            spent = 0.0
    else:
        try:
            response = httpx.get(
                "http://127.0.0.1:4000/global/spend",
                headers={"Authorization": f"Bearer {settings.litellm_api_key}"},
                timeout=2.0,
            )
            if response.status_code == 200:
                payload = response.json()
                spent = float(payload.get("spend", 0.0))
        except httpx.HTTPError:
            spent = 0.0

    return {
        "spent_usd": round(spent, 4),
        "budget_usd": cap,
        "remaining_usd": round(max(cap - spent, 0.0), 4),
    }


def collect_telemetry() -> dict[str, Any]:
    return {
        "gpu": read_gpu_stats(),
        "containers": read_container_status(),
        "openrouter": read_openrouter_spend(),
        "validated_pairs": count_validated_pairs(),
    }
