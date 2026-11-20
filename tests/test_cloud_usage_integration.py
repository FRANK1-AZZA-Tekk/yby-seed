"""Validação integrada FinOps (#42) — provedores simulados, sem HTTP pago."""

from __future__ import annotations

import json
import time
from pathlib import Path

from click.testing import CliRunner

from src.engine.budget import CloudBudget
from src.engine.cache import ResponseCache
from src.engine.cloud_cli import cloud_cli
from src.engine.cloud_pricing import estimate_cost
from src.engine.cloud_usage_db import CloudUsageRegistry
from src.engine.cloud_usage_log import (
    EVENT_COMPLETED,
    CloudUsageLog,
    utc_timestamp,
)
from src.engine.cloud_usage_report import build_cloud_usage_report, format_cloud_usage_report
from src.engine.config import EngineConfig
from src.engine.hybrid import HybridEngine
from src.engine.providers import ProviderError
from src.engine.routing import DEFAULT_HEAVY_PHRASES
from src.main import cli


class FakeOllama:
    def __init__(self, text: str = "local-ok", error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls: list[str] = []

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        self.calls.append(prompt)
        if self.error is not None:
            raise self.error
        return self.text


class FakeCloud:
    def __init__(self, text: str = "cloud-ok") -> None:
        self.text = text
        self.calls: list[str] = []

    def has_credentials(self) -> bool:
        return True

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        self.calls.append(prompt)
        return self.text


def _config(*, cloud_model: str = "openrouter/free") -> EngineConfig:
    return EngineConfig(
        ollama_base_url="http://ollama.test",
        local_model="qwen2.5-coder:3b",
        cloud_base_url="https://openrouter.ai/api/v1",
        cloud_model=cloud_model,
        cloud_api_key="test-key",
        cloud_fallback_base_url="https://api.x.ai/v1",
        cloud_fallback_model="grok-4.7",
        cloud_fallback_api_key="",
        heavy_min_chars=1200,
        heavy_min_lines=25,
        heavy_min_questions=3,
        heavy_phrases=DEFAULT_HEAVY_PHRASES,
        ollama_timeout=5.0,
        cloud_timeout=5.0,
        cache_ttl_seconds=60.0,
        cloud_max_chars=12000,
    )


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = {
        "YBY_CLOUD_DB_PATH": str(tmp_path / "cloud.sqlite3"),
        "YBY_CLOUD_LOG_PATH": str(tmp_path / "cloud.jsonl"),
        "YBY_CLOUD_JSONL_MIRROR": "0",
        "YBY_CLOUD_MODE": "ask",
        "YBY_CLOUD_REQUIRE_CONFIRM": "0",
        "YBY_CLOUD_ALLOW_NO_TTY": "1",
        "YBY_CLOUD_ALLOW_VAULT": "0",
        "YBY_CLOUD_MONTHLY_COST_USD_LIMIT": "10.00",
        "YBY_CLOUD_DAILY_COST_USD_LIMIT": "2.00",
        "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "200000",
        "YBY_CLOUD_DAILY_TOKEN_LIMIT": "50000",
        "YBY_CLOUD_WARN_TOKEN_LIMIT": "150000",
        "YBY_CLOUD_WARN_DAILY_TOKEN_LIMIT": "40000",
    }
    env.update(extra)
    return env


def _engine(
    tmp_path: Path,
    env: dict[str, str],
    *,
    ollama: FakeOllama | None = None,
    cloud: FakeCloud | None = None,
    confirm: bool = True,
) -> tuple[HybridEngine, FakeCloud, FakeOllama]:
    cloud = cloud or FakeCloud()
    ollama = ollama or FakeOllama()
    log = CloudUsageLog.from_env(env)
    budget = CloudBudget.from_env(env)
    engine = HybridEngine(
        _config(),
        ollama,
        cloud,
        cache=ResponseCache(ttl_seconds=60.0),
        cloud_log=log,
        budget=budget,
        confirm_fn=lambda _msg: confirm,
        has_tty_fn=lambda: True,
    )
    return engine, cloud, ollama


def test_import_jsonl_twice_idempotent(tmp_path: Path) -> None:
    jsonl = tmp_path / "hist.jsonl"
    ts = 1_700_000_100.0
    event = {
        "timestamp": ts,
        "provider": "openrouter",
        "model": "openrouter/free",
        "purpose": "route_cloud",
        "input_tokens_estimate": 20,
        "output_tokens_estimate": 5,
        "estimated_cost_usd": 0.0,
        "result": EVENT_COMPLETED,
    }
    jsonl.write_text(json.dumps(event) + "\n", encoding="utf-8")
    reg = CloudUsageRegistry(tmp_path / "db.sqlite3")
    first = reg.import_jsonl(jsonl)
    second = reg.import_jsonl(jsonl)
    assert first.imported_n == 1
    assert second.imported_n == 0
    assert second.skipped_n == 1
    assert reg.count_events() == 1
    totals = reg.sum_completed_usage(now=ts)
    assert totals.day_tokens == 25
    reg.close()


def test_no_double_count_mirror_coexistence(tmp_path: Path) -> None:
    """Com DB presente, budget não soma JSONL mesmo com mirror ligado."""

    env = _env(tmp_path, YBY_CLOUD_JSONL_MIRROR="1")
    log = CloudUsageLog.from_env(env)
    event = {
        "timestamp": utc_timestamp(),
        "provider": "openrouter",
        "model": "openrouter/free",
        "purpose": "route_cloud",
        "input_tokens_estimate": 100,
        "output_tokens_estimate": 50,
        "estimated_cost_usd": 0.0,
        "result": EVENT_COMPLETED,
    }
    log.append(event)
    # Espelho JSONL existe; se budget somasse os dois, tokens dobrariam.
    assert Path(env["YBY_CLOUD_LOG_PATH"]).is_file()
    budget = CloudBudget.from_env(env)
    day_t, month_t, _day_c, _month_c = budget._usage()
    assert day_t == 150
    assert month_t == 150


def test_usage_visible_immediately_after_write(tmp_path: Path) -> None:
    env = _env(tmp_path)
    log = CloudUsageLog.from_env(env)
    budget = CloudBudget.from_env(env)
    before = budget._usage()
    assert before[0] == 0
    log.append(
        {
            "timestamp": utc_timestamp(),
            "provider": "openrouter",
            "model": "openrouter/free",
            "purpose": "route_cloud",
            "input_tokens_estimate": 40,
            "output_tokens_estimate": 10,
            "estimated_cost_usd": 0.0,
            "result": EVENT_COMPLETED,
        }
    )
    day_t, month_t, *_ = budget._usage()
    assert day_t == 50
    assert month_t == 50


def test_warn_allows_block_denies_provider(tmp_path: Path, monkeypatch) -> None:
    # Bloqueio: teto diário já estourado → sem chamada.
    env_block = _env(
        tmp_path,
        YBY_CLOUD_DAILY_TOKEN_LIMIT="10",
        YBY_CLOUD_WARN_DAILY_TOKEN_LIMIT="5",
        YBY_CLOUD_REQUIRE_CONFIRM="0",
    )
    for key, value in env_block.items():
        monkeypatch.setenv(key, value)
    log = CloudUsageLog.from_env(env_block)
    log.append(
        {
            "timestamp": utc_timestamp(),
            "provider": "openrouter",
            "model": "openrouter/free",
            "purpose": "seed",
            "input_tokens_estimate": 20,
            "output_tokens_estimate": 0,
            "estimated_cost_usd": 0.0,
            "result": EVENT_COMPLETED,
        }
    )
    engine, cloud, ollama = _engine(tmp_path, env_block)
    reply = engine.reply("pensa mais: bloquear orcamento", explicit_heavy=True)
    assert cloud.calls == []
    assert reply.provider == "local"
    assert ollama.calls  # fallback local após block
    # Evento blocked_budget no registry
    reg = CloudUsageRegistry(Path(env_block["YBY_CLOUD_DB_PATH"]))
    by_status = reg.count_by_status()
    assert by_status.get("blocked_budget", 0) >= 1
    reg.close()

    # Aviso: abaixo do hard, acima do warn → permite HTTP (confirm mock True).
    warn_dir = tmp_path / "warn"
    warn_dir.mkdir()
    env_warn = _env(
        warn_dir,
        YBY_CLOUD_DAILY_TOKEN_LIMIT="1000",
        YBY_CLOUD_WARN_DAILY_TOKEN_LIMIT="10",
        YBY_CLOUD_REQUIRE_CONFIRM="0",
    )
    for key, value in env_warn.items():
        monkeypatch.setenv(key, value)
    log_w = CloudUsageLog.from_env(env_warn)
    log_w.append(
        {
            "timestamp": utc_timestamp(),
            "provider": "openrouter",
            "model": "openrouter/free",
            "purpose": "seed",
            "input_tokens_estimate": 20,
            "output_tokens_estimate": 0,
            "estimated_cost_usd": 0.0,
            "result": EVENT_COMPLETED,
        }
    )
    engine_w, cloud_w, _ollama_w = _engine(warn_dir, env_warn)
    reply_w = engine_w.reply("pensa mais: aviso de orcamento", explicit_heavy=True)
    assert len(cloud_w.calls) == 1
    assert reply_w.provider == "cloud"
    assert reply_w.notice is not None
    assert reply_w.notice.startswith("Aviso:")


def test_cache_hit_no_second_provider_call(tmp_path: Path, monkeypatch) -> None:
    env = _env(tmp_path, YBY_CLOUD_REQUIRE_CONFIRM="0")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    engine, cloud, _ollama = _engine(tmp_path, env)
    prompt = "pensa mais: cache integration"
    first = engine.reply(prompt, explicit_heavy=True)
    assert first.provider == "cloud"
    assert len(cloud.calls) == 1
    completed_before = CloudUsageRegistry(Path(env["YBY_CLOUD_DB_PATH"])).count_by_status()
    second = engine.reply(prompt, explicit_heavy=True)
    assert second.provider == "cloud"
    assert len(cloud.calls) == 1  # sem nova cobrança/HTTP
    completed_after = CloudUsageRegistry(Path(env["YBY_CLOUD_DB_PATH"])).count_by_status()
    assert completed_after.get("completed") == completed_before.get("completed")


def test_vault_block_no_provider_call(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "segredo.md"
    note.write_text("privado", encoding="utf-8")
    env = _env(
        tmp_path,
        YBY_CLOUD_ALLOW_VAULT="0",
        YBY_VAULT_PATH=str(vault),
        YBY_CLOUD_REQUIRE_CONFIRM="0",
    )
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    engine, cloud, ollama = _engine(tmp_path, env)
    reply = engine.reply(f"pensa mais: leia {note.resolve()}", explicit_heavy=True)
    assert cloud.calls == []
    assert reply.provider == "local"
    assert ollama.calls
    reg = CloudUsageRegistry(Path(env["YBY_CLOUD_DB_PATH"]))
    assert reg.count_by_status().get("blocked_authz", 0) >= 1
    reg.close()


def test_ollama_fail_does_not_call_cloud(tmp_path: Path, monkeypatch) -> None:
    env = _env(tmp_path)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    ollama = FakeOllama(error=ProviderError("ollama down"))
    engine, cloud, _ = _engine(tmp_path, env, ollama=ollama)
    reply = engine.reply("ola curto")  # rota local
    assert reply.provider == "none"
    assert cloud.calls == []
    assert "Nuvem não é acionada" in (reply.notice or "")


def test_report_matches_budget_same_history(tmp_path: Path, monkeypatch) -> None:
    env = _env(tmp_path)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    log = CloudUsageLog.from_env(env)
    known = estimate_cost(
        provider="openrouter",
        model="nousresearch/hermes-4-70b",
        input_tokens=1_000,
        output_tokens=500,
    )
    unknown = estimate_cost(
        provider="openrouter",
        model="vendor/mystery-paid-model-xyz",
        input_tokens=1_000,
        output_tokens=0,
    )
    assert known.basis == "known"
    assert unknown.basis == "unknown_conservative"
    assert unknown.usd > 0.0  # nunca zero conhecido
    log.append(
        {
            "timestamp": utc_timestamp(),
            "provider": "openrouter",
            "model": "nousresearch/hermes-4-70b",
            "purpose": "route_cloud",
            "input_tokens_estimate": 1000,
            "output_tokens_estimate": 500,
            "estimated_cost_usd": known.usd,
            "result": EVENT_COMPLETED,
            "meta": {"token_basis": "estimated", "cost_basis": known.basis},
        }
    )
    log.append(
        {
            "timestamp": utc_timestamp(),
            "provider": "openrouter",
            "model": "vendor/mystery-paid-model-xyz",
            "purpose": "route_cloud",
            "input_tokens_estimate": 1000,
            "output_tokens_estimate": 0,
            "estimated_cost_usd": unknown.usd,
            "result": EVENT_COMPLETED,
            "meta": {"token_basis": "estimated", "cost_basis": unknown.basis},
        }
    )
    budget = CloudBudget.from_env(env)
    day_t, month_t, day_c, month_c = budget._usage()
    report = build_cloud_usage_report(env)
    assert report.day_tokens == day_t == month_t == 2500
    assert report.day_cost_usd == day_c
    assert report.month_cost_usd == month_c
    assert report.month_cost_usd == known.usd + unknown.usd
    text = format_cloud_usage_report(report)
    assert "não são a fatura do provedor" in text
    runner = CliRunner()
    result = runner.invoke(cli, ["cloud", "report"])
    assert result.exit_code == 0, result.output
    assert "events: 2" in result.output


def test_cli_prune_dry_run_fingerprint(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "cloud.sqlite3"
    reg = CloudUsageRegistry(db)
    now = time.time()
    old = now - (200 * 86400)
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
            "timestamp": now,
            "provider": "openrouter",
            "model": "m",
            "purpose": "t",
            "input_tokens_estimate": 2,
            "output_tokens_estimate": 0,
            "result": EVENT_COMPLETED,
        }
    )
    before = reg.fingerprint()
    reg.close()

    monkeypatch.setenv("YBY_CLOUD_DB_PATH", str(db))
    monkeypatch.setenv("YBY_CLOUD_LOG_PATH", str(tmp_path / "x.jsonl"))
    monkeypatch.setenv("YBY_CLOUD_RETENTION_DAYS", "90")

    runner = CliRunner()
    dry = runner.invoke(cloud_cli, ["prune", "--dry-run", "--days", "90"])
    assert dry.exit_code == 0, dry.output
    assert "candidatos" in dry.output

    after_reg = CloudUsageRegistry(db)
    assert after_reg.fingerprint() == before
    after_reg.close()


def test_unknown_tariff_not_displayed_as_known_zero() -> None:
    est = estimate_cost(
        provider="openrouter",
        model="vendor/no-price-here",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert est.basis == "unknown_conservative"
    assert est.usd == 3.0
    free = estimate_cost(
        provider="openrouter",
        model="openrouter/free",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert free.basis == "free"
    assert free.usd == 0.0
