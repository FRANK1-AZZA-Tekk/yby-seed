"""Ledger de missões — economia local (GTX 1650) vs nuvem."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from src.yby_seed.agents.state import MissionState, MissionStatus
from src.yby_seed.config import get_settings
from src.yby_seed.runtime import resources
from src.yby_seed.telemetry import count_validated_pairs, read_openrouter_spend

logger = logging.getLogger(__name__)

# Estimativa conservadora por missão quando roteada via OpenRouter (USD).
_CLOUD_MISSION_USD = 0.012
_LOCAL_MISSION_USD = 0.0

_LOCAL_FALLBACK_ROWS: list[dict[str, Any]] = []

_SCHEMA_ENSURED = False


def _is_local_model(model_routed: str) -> bool:
    lowered = model_routed.lower()
    return "local" in lowered or lowered.startswith("yby-local") or "ollama" in lowered


async def _ensure_schema(pool) -> None:
    global _SCHEMA_ENSURED
    if _SCHEMA_ENSURED:
        return
    ddl = """
    CREATE TABLE IF NOT EXISTS mission_ledger (
        id BIGSERIAL PRIMARY KEY,
        mission_id TEXT NOT NULL,
        domain TEXT NOT NULL,
        board TEXT NOT NULL DEFAULT '',
        model_routed TEXT NOT NULL,
        cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
        attempts INTEGER NOT NULL DEFAULT 0,
        latency_ms INTEGER NOT NULL DEFAULT 0,
        estimated_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
        status TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """
    async with pool.connection() as conn:
        await conn.execute(ddl)
        await conn.commit()
    _SCHEMA_ENSURED = True


async def record_mission_completion(
    state: MissionState,
    *,
    model_routed: str | None = None,
    cache_hit: bool = False,
    latency_ms: int = 0,
    board: str = "",
) -> None:
    """Registra missão concluída (pool PostgreSQL ou fallback em memória)."""
    if state.status != MissionStatus.SUCCESS:
        return

    settings = get_settings()
    model = model_routed or settings.litellm_model
    cost = _LOCAL_MISSION_USD if _is_local_model(model) else _CLOUD_MISSION_USD

    row = {
        "mission_id": state.mission_id,
        "domain": state.domain,
        "board": board,
        "model_routed": model,
        "cache_hit": cache_hit,
        "attempts": state.attempt_count,
        "latency_ms": latency_ms,
        "estimated_cost_usd": cost,
        "status": state.status.value,
        "created_at": datetime.now(UTC).isoformat(),
    }

    pool = resources.get_pg_pool()
    if pool is None:
        _LOCAL_FALLBACK_ROWS.append(row)
        return

    try:
        await _ensure_schema(pool)
        query = """
            INSERT INTO mission_ledger (
                mission_id, domain, board, model_routed, cache_hit,
                attempts, latency_ms, estimated_cost_usd, status
            ) VALUES (
                %(mission_id)s, %(domain)s, %(board)s, %(model_routed)s, %(cache_hit)s,
                %(attempts)s, %(latency_ms)s, %(estimated_cost_usd)s, %(status)s
            )
        """
        async with pool.connection() as conn:
            await conn.execute(query, row)
            await conn.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ledger PG indisponível, fallback memória: %s", exc)
        _LOCAL_FALLBACK_ROWS.append(row)


class MissionTimer:
    """Helper para medir latência de missão."""

    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)


async def get_economy_stats() -> dict[str, Any]:
    """Estatísticas de roteamento local vs nuvem e teto OpenRouter."""
    local_count = 0
    cloud_count = 0
    ledger_cloud_usd = 0.0
    total = 0

    pool = resources.get_pg_pool()
    if pool is not None:
        try:
            await _ensure_schema(pool)
            query = """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (
                        WHERE model_routed ILIKE '%%local%%'
                           OR model_routed ILIKE 'yby-local%%'
                           OR model_routed ILIKE '%%ollama%%'
                    ) AS local_n,
                    COUNT(*) FILTER (
                        WHERE NOT (
                            model_routed ILIKE '%%local%%'
                            OR model_routed ILIKE 'yby-local%%'
                            OR model_routed ILIKE '%%ollama%%'
                        )
                    ) AS cloud_n,
                    COALESCE(SUM(estimated_cost_usd), 0) AS cost_sum
                FROM mission_ledger
                WHERE status = 'success'
            """
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    row = await cur.fetchone()
            if row:
                total = int(row[0] or 0)
                local_count = int(row[1] or 0)
                cloud_count = int(row[2] or 0)
                ledger_cloud_usd = float(row[3] or 0.0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("ledger stats PG: %s", exc)

    if total == 0 and _LOCAL_FALLBACK_ROWS:
        for row in _LOCAL_FALLBACK_ROWS:
            if row.get("status") != "success":
                continue
            total += 1
            if _is_local_model(str(row.get("model_routed", ""))):
                local_count += 1
            else:
                cloud_count += 1
                ledger_cloud_usd += float(row.get("estimated_cost_usd", 0.0))

    openrouter = read_openrouter_spend()
    monthly_spend = float(openrouter.get("spent_usd", 0.0))
    budget_cap = float(openrouter.get("budget_usd", get_settings().openrouter_monthly_budget_usd))

    if total > 0:
        local_pct = round(100.0 * local_count / total, 1)
        cloud_pct = round(100.0 * cloud_count / total, 1)
    else:
        local_pct = 100.0
        cloud_pct = 0.0

    cloud_avoided = cloud_count * _CLOUD_MISSION_USD
    estimated_savings = round(max(cloud_avoided - ledger_cloud_usd, 0.0), 4)

    return {
        "total_missions": total,
        "local_missions": local_count,
        "cloud_missions": cloud_count,
        "local_pct": local_pct,
        "cloud_pct": cloud_pct,
        "estimated_savings_usd": estimated_savings,
        "ledger_cloud_cost_usd": round(ledger_cloud_usd, 4),
        "monthly_spend_usd": monthly_spend,
        "budget_cap_usd": budget_cap,
        "budget_remaining_usd": round(max(budget_cap - monthly_spend, 0.0), 4),
        "validated_pairs": count_validated_pairs(),
        "gpu_profile": "GTX 1650 (local-first)",
    }


def reset_local_ledger_for_tests() -> None:
    """Limpa fallback em memória (apenas testes)."""
    _LOCAL_FALLBACK_ROWS.clear()
    global _SCHEMA_ENSURED
    _SCHEMA_ENSURED = False
