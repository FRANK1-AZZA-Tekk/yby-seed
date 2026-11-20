"""S1 / #42: registry SQLite + import JSONL + dual-write (T8/T14)."""

from __future__ import annotations

import json
import stat
import time

import pytest

from src.engine.cloud_usage_db import (
    CloudUsageRegistry,
    status_from_result,
)
from src.engine.cloud_usage_log import (
    EVENT_COMPLETED,
    EVENT_REQUESTED,
    CloudUsageLog,
    utc_timestamp,
)


def _completed_event(**extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "timestamp": utc_timestamp(),
        "provider": "openrouter",
        "model": "openrouter/free",
        "purpose": "route_cloud",
        "input_tokens_estimate": 100,
        "output_tokens_estimate": 20,
        "estimated_cost_usd": 0.0,
        "result": EVENT_COMPLETED,
    }
    base.update(extra)
    return base


def test_status_mapping_roundtrip() -> None:
    assert status_from_result(EVENT_COMPLETED) == "completed"
    assert status_from_result("completed") == "completed"
    with pytest.raises(ValueError):
        status_from_result("nope")


def test_registry_schema_and_permissions(tmp_path) -> None:
    db_path = tmp_path / "cloud_usage.sqlite3"
    reg = CloudUsageRegistry(db_path)
    reg.insert_event(_completed_event())
    assert db_path.is_file()
    mode = stat.S_IMODE(db_path.stat().st_mode)
    assert mode == 0o600
    assert reg.count_events() == 1
    totals = reg.sum_completed_usage()
    assert totals.day_tokens == 120
    assert totals.month_tokens == 120
    reg.close()


def test_insert_rejects_forbidden_fields(tmp_path) -> None:
    reg = CloudUsageRegistry(tmp_path / "db.sqlite3")
    # Valor dummy — o gate rejeita a *chave* api_key, não o formato do valor.
    bad = _completed_event(api_key="TEST_FORBIDDEN_FIELD")
    with pytest.raises(ValueError, match="proibido"):
        reg.insert_event(bad)


def test_import_jsonl_t8(tmp_path) -> None:
    jsonl = tmp_path / "cloud_usage.jsonl"
    lines = [
        json.dumps(_completed_event(input_tokens_estimate=10, output_tokens_estimate=5)),
        "not-json",
        json.dumps({"timestamp": time.time()}),  # incompleto
        json.dumps(
            _completed_event(
                input_tokens_estimate=30,
                output_tokens_estimate=0,
                estimated_cost_usd=0.5,
            )
        ),
    ]
    jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")
    reg = CloudUsageRegistry(tmp_path / "db.sqlite3")
    report = reg.import_jsonl(jsonl)
    assert report.imported_n == 2
    assert report.skipped_n == 2
    assert report.last_timestamp is not None
    assert reg.count_events() == 2
    totals = reg.sum_completed_usage()
    assert totals.day_tokens == 45
    assert totals.day_cost_usd == pytest.approx(0.5)


def test_import_jsonl_if_empty_only_once(tmp_path) -> None:
    jsonl = tmp_path / "cloud_usage.jsonl"
    jsonl.write_text(json.dumps(_completed_event()) + "\n", encoding="utf-8")
    reg = CloudUsageRegistry(tmp_path / "db.sqlite3")
    first = reg.import_jsonl_if_empty(jsonl)
    assert first is not None and first.imported_n == 1
    second = reg.import_jsonl_if_empty(jsonl)
    assert second is None
    assert reg.count_events() == 1


def test_import_jsonl_twice_dedupes(tmp_path) -> None:
    jsonl = tmp_path / "cloud_usage.jsonl"
    event = _completed_event(input_tokens_estimate=7, output_tokens_estimate=3)
    jsonl.write_text(json.dumps(event) + "\n", encoding="utf-8")
    reg = CloudUsageRegistry(tmp_path / "db.sqlite3")
    first = reg.import_jsonl(jsonl)
    second = reg.import_jsonl(jsonl)
    assert first.imported_n == 1
    assert second.imported_n == 0
    assert second.skipped_n == 1
    assert reg.count_events() == 1
    assert reg.sum_completed_usage().day_tokens == 10


def test_facade_dual_write_t14(tmp_path) -> None:
    jsonl = tmp_path / "cloud_usage.jsonl"
    db_path = tmp_path / "cloud_usage.sqlite3"
    reg = CloudUsageRegistry(db_path)
    log = CloudUsageLog(jsonl, registry=reg, jsonl_mirror=True, db_enabled=True)
    log.append(
        {
            "timestamp": utc_timestamp(),
            "provider": "openrouter",
            "model": "m",
            "purpose": "route_cloud",
            "input_tokens_estimate": 11,
            "output_tokens_estimate": 2,
            "result": EVENT_REQUESTED,
        }
    )
    assert jsonl.is_file()
    assert db_path.is_file()
    assert reg.count_events() == 1
    line = json.loads(jsonl.read_text(encoding="utf-8").strip())
    assert line["result"] == EVENT_REQUESTED


def test_facade_from_env_enables_db_and_mirror(tmp_path) -> None:
    jsonl = tmp_path / "usage.jsonl"
    db_path = tmp_path / "usage.sqlite3"
    # JSONL pré-existente → import one-shot na primeira append
    jsonl.write_text(json.dumps(_completed_event()) + "\n", encoding="utf-8")
    log = CloudUsageLog.from_env(
        {
            "YBY_CLOUD_LOG_PATH": str(jsonl),
            "YBY_CLOUD_DB_PATH": str(db_path),
            "YBY_CLOUD_JSONL_MIRROR": "1",
        }
    )
    assert log.db_enabled is True
    assert log.registry is not None
    log.append(
        {
            "timestamp": utc_timestamp(),
            "provider": "openrouter",
            "model": "m",
            "purpose": "route_cloud",
            "input_tokens_estimate": 1,
            "output_tokens_estimate": 0,
            "result": EVENT_REQUESTED,
        }
    )
    # 1 importado + 1 novo
    assert log.registry.count_events() == 2
    # mirror appends another JSONL line
    assert len(jsonl.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_facade_from_env_mirror_defaults_off(tmp_path) -> None:
    """S5: YBY_CLOUD_JSONL_MIRROR default = off (só SQLite)."""

    jsonl = tmp_path / "usage.jsonl"
    db_path = tmp_path / "usage.sqlite3"
    log = CloudUsageLog.from_env(
        {
            "YBY_CLOUD_LOG_PATH": str(jsonl),
            "YBY_CLOUD_DB_PATH": str(db_path),
        }
    )
    assert log.jsonl_mirror is False
    log.append(
        {
            "timestamp": utc_timestamp(),
            "provider": "openrouter",
            "model": "m",
            "purpose": "route_cloud",
            "input_tokens_estimate": 1,
            "output_tokens_estimate": 0,
            "result": EVENT_REQUESTED,
        }
    )
    assert log.registry is not None
    assert log.registry.count_events() == 1
    assert not jsonl.exists()


def test_registry_prune_retention_s5(tmp_path) -> None:
    """S5: prune remove completed/failed antigos; mantém blocked."""

    from src.engine.cloud_usage_db import retention_days_from_env
    from src.engine.cloud_usage_log import EVENT_BLOCKED_AUTHZ, EVENT_FAILED

    assert retention_days_from_env({}) == 90
    assert retention_days_from_env({"YBY_CLOUD_RETENTION_DAYS": "30"}) == 30

    reg = CloudUsageRegistry(tmp_path / "db.sqlite3")
    now = 1_700_000_000.0
    old = now - (100 * 86400)
    recent = now - (10 * 86400)
    reg.insert_event(
        {
            "timestamp": old,
            "provider": "openrouter",
            "model": "m",
            "purpose": "t",
            "input_tokens_estimate": 1,
            "output_tokens_estimate": 0,
            "result": EVENT_COMPLETED,
        }
    )
    reg.insert_event(
        {
            "timestamp": old,
            "provider": "openrouter",
            "model": "m",
            "purpose": "t",
            "input_tokens_estimate": 1,
            "output_tokens_estimate": 0,
            "result": EVENT_FAILED,
        }
    )
    reg.insert_event(
        {
            "timestamp": old,
            "provider": "openrouter",
            "model": "m",
            "purpose": "t",
            "input_tokens_estimate": 1,
            "output_tokens_estimate": 0,
            "result": EVENT_BLOCKED_AUTHZ,
        }
    )
    reg.insert_event(
        {
            "timestamp": recent,
            "provider": "openrouter",
            "model": "m",
            "purpose": "t",
            "input_tokens_estimate": 1,
            "output_tokens_estimate": 0,
            "result": EVENT_COMPLETED,
        }
    )
    deleted = reg.prune(retention_days=90, now=now)
    assert deleted == 2
    assert reg.count_events() == 2  # blocked + recent completed
    reg.close()


def test_facade_can_disable_db(tmp_path) -> None:
    jsonl = tmp_path / "only.jsonl"
    log = CloudUsageLog.from_env(
        {
            "YBY_CLOUD_LOG_PATH": str(jsonl),
            "YBY_CLOUD_DB_PATH": "off",
            "YBY_CLOUD_JSONL_MIRROR": "0",
        }
    )
    assert log.db_enabled is False
    log.append(
        {
            "timestamp": utc_timestamp(),
            "provider": "openrouter",
            "model": "m",
            "purpose": "t",
            "input_tokens_estimate": 1,
            "output_tokens_estimate": 0,
            "result": EVENT_COMPLETED,
        }
    )
    assert jsonl.is_file()
    assert not (tmp_path / "usage.sqlite3").exists()


def test_jsonl_only_ctor_keeps_legacy_tests_working(tmp_path) -> None:
    """CloudUsageLog(path) sem registry → só JSONL (compat testes antigos)."""

    log = CloudUsageLog(tmp_path / "legacy.jsonl")
    log.append(
        {
            "timestamp": utc_timestamp(),
            "provider": "openrouter",
            "model": "m",
            "purpose": "t",
            "input_tokens_estimate": 1,
            "output_tokens_estimate": 0,
            "result": EVENT_COMPLETED,
        }
    )
    assert (tmp_path / "legacy.jsonl").is_file()
    mode = stat.S_IMODE((tmp_path / "legacy.jsonl").stat().st_mode)
    assert mode == 0o600
