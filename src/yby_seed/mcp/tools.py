"""Ferramentas MCP auditáveis (pgvector, repo local, GPU, MQTT, Vast dry-run)."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
import psycopg
from openai import OpenAI

from src.yby_seed.config import Settings, get_settings
from src.yby_seed.forge import vast_router
from src.yby_seed.memory.retriever import EMBED_MODEL
from src.yby_seed.runtime import resources
from src.yby_seed.runtime.gpu_sync import sync_inference_slot
from src.yby_seed.telemetry import read_gpu_stats

AUDIT_PATH = Path("data/mcp/audit.jsonl")
CMD_TOPIC_PREFIX = "yby/seed/cmd/"
FORBIDDEN_MQTT_KEYS = frozenset({"rm", "shutdown", "destroy", "format", "sudo", "exec"})
FORBIDDEN_PATH_PARTS = frozenset({".git", ".env", "/etc", "/root", "/proc", "/sys"})
USD_BRL_DEFAULT = 5.45
GTX_VRAM_MB = 4096
MIN_FREE_VRAM_MB = 768


def _audit(tool: str, details: dict[str, Any]) -> None:
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "tool": tool,
        "details": details,
    }
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        return


def _allowed_roots(settings: Settings) -> list[Path]:
    raw = os.environ.get("YBY_MCP_REPO_ROOTS", "").strip()
    if raw:
        return [Path(part).resolve() for part in raw.split(":") if part.strip()]
    return [Path.cwd().resolve(), Path("/agent/repos/yby-seed").resolve()]


def _resolve_safe_path(repo_path: str, settings: Settings) -> Path:
    raw = repo_path.strip()
    if any(part in raw for part in FORBIDDEN_PATH_PARTS):
        raise PermissionError("segmento de caminho proibido")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve(strict=False)

    for root in _allowed_roots(settings):
        try:
            candidate.relative_to(root)
            if ".." in candidate.parts:
                raise PermissionError("path traversal detectado")
            return candidate
        except ValueError:
            continue
    raise PermissionError("path fora dos diretórios autorizados (path traversal bloqueado)")


async def search_knowledge_base(query: str, domain: str | None = None) -> dict[str, Any]:
    """Consulta pgvector e devolve chunks ranqueados."""
    settings = get_settings()
    client = OpenAI(base_url=settings.litellm_base_url, api_key=settings.litellm_api_key)
    with sync_inference_slot():
        vector = client.embeddings.create(model=EMBED_MODEL, input=query).data[0].embedding

    sql = """
        SELECT source_file, domain, content
        FROM knowledge_chunks
        WHERE (%s::text IS NULL OR domain = %s)
        ORDER BY embedding <=> %s::vector
        LIMIT 6
    """
    chunks: list[dict[str, str]] = []
    try:
        with psycopg.connect(resources.database_url()) as conn:
            rows = conn.execute(sql, (domain, domain, vector)).fetchall()
            for source_file, dom, content in rows:
                chunks.append(
                    {
                        "source_file": source_file,
                        "domain": dom,
                        "content": content[:2000],
                    }
                )
    except Exception as exc:  # noqa: BLE001
        _audit("search_knowledge_base", {"query": query, "error": str(exc)})
        return {"query": query, "domain": domain, "chunks": [], "error": str(exc)}

    _audit("search_knowledge_base", {"query": query, "domain": domain, "count": len(chunks)})
    return {"query": query, "domain": domain, "chunks": chunks}


def inspect_local_repo(repo_path: str, file_pattern: str) -> dict[str, Any]:
    """Lista arquivos locais autorizados (sem path traversal)."""
    settings = get_settings()
    root = _resolve_safe_path(repo_path, settings)
    if not root.exists():
        raise FileNotFoundError(f"repo não encontrado: {root}")

    pattern = file_pattern.strip() or "**/*"
    if ".." in pattern or pattern.startswith("/"):
        raise PermissionError("file_pattern inválido")

    files: list[str] = []
    for path in sorted(root.glob(pattern)):
        if not path.is_file():
            continue
        resolved = path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise PermissionError("symlink/path escape bloqueado") from exc
        rel = str(resolved.relative_to(root))
        if len(files) >= 200:
            break
        files.append(rel)

    payload = {
        "repo_path": str(root),
        "file_pattern": pattern,
        "file_count": len(files),
        "files": files,
    }
    _audit("inspect_local_repo", {"repo_path": str(root), "file_count": len(files)})
    return payload


def check_gpu_headroom() -> dict[str, Any]:
    """VRAM livre na GTX 1650 — decide local vs fila/fallback."""
    stats = read_gpu_stats()
    total = int(stats.get("vram_total_mb") or GTX_VRAM_MB)
    used = int(stats.get("vram_used_mb") or 0)
    free = max(total - used, 0)

    if not stats.get("available"):
        decision = "queue_or_fallback"
        reason = "nvidia-smi indisponível"
    elif free < MIN_FREE_VRAM_MB:
        decision = "queue_or_fallback"
        reason = f"VRAM livre {free}MB < mínimo {MIN_FREE_VRAM_MB}MB"
    else:
        decision = "process_local"
        reason = f"VRAM livre {free}MB"

    payload = {
        "gpu": stats,
        "vram_free_mb": free,
        "vram_cap_mb": GTX_VRAM_MB,
        "decision": decision,
        "reason": reason,
    }
    _audit("check_gpu_headroom", payload)
    return payload


def publish_mqtt_command(topic: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Publica comando validado no Mosquitto (`yby/seed/cmd/...`)."""
    if not topic.startswith(CMD_TOPIC_PREFIX):
        raise PermissionError(f"tópico deve começar com {CMD_TOPIC_PREFIX}")
    if any(key in payload for key in FORBIDDEN_MQTT_KEYS):
        raise PermissionError("payload contém chaves destrutivas bloqueadas")

    settings = get_settings()
    body = json.dumps(payload, ensure_ascii=False)
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=30)
        info = client.publish(topic, body, qos=1)
        client.disconnect()
        result = {"topic": topic, "published": bool(info.rc == mqtt.MQTT_ERR_SUCCESS)}
    except Exception as exc:  # noqa: BLE001
        result = {"topic": topic, "published": False, "error": str(exc)}

    _audit("publish_mqtt_command", result)
    return result


def simulate_vast_forge(task: str) -> dict[str, Any]:
    """Executa vast_router em dry-run e estima TCO USD/BRL."""
    mission = task if task in vast_router.MISSION_PROFILES else "rag-embed"
    profile = vast_router.MISSION_PROFILES[mission]
    plan = vast_router.run_mission(mission, max_usd=profile["default_max_usd"], dry_run=True)

    usd_rate = float(os.environ.get("YBY_USD_BRL", USD_BRL_DEFAULT))
    offers = plan.get("offers") or []
    best_tco = min((item.get("tco_hourly", 0.0) for item in offers), default=0.0)

    payload = {
        "task": task,
        "mission": mission,
        "dry_run": True,
        "best_tco_usd_hour": round(best_tco, 4),
        "best_tco_brl_hour": round(best_tco * usd_rate, 4),
        "offers": offers,
        "plan": plan,
    }
    _audit("simulate_vast_forge", {"mission": mission, "best_tco_usd_hour": best_tco})
    return payload
