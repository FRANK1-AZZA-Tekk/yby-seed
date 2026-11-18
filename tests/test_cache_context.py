"""Cache de respostas e limite de contexto."""

from __future__ import annotations

import json
import time
from pathlib import Path

from src.engine.budget import CloudBudget
from src.engine.cache import ResponseCache
from src.engine.cloud_usage_log import EVENT_COMPLETED
from src.engine.context import trim_context
from src.engine.hybrid import HybridEngine, engine_from_env
from tests.test_engine import FakeCloud, FakeOllama, _config


def test_trim_context_nao_corta_texto_curto() -> None:
    assert trim_context("oi", 100) == "oi"


def test_trim_context_marca_corte() -> None:
    text = "A" * 40 + "MEIO" + "B" * 40
    out = trim_context(text, 50)
    assert len(out) <= 50
    assert "truncado" in out
    assert out.startswith("A")
    assert out.endswith("B")


def test_trim_context_max_zero_nao_corta() -> None:
    assert trim_context("abcdefgh", 0) == "abcdefgh"


def test_cache_hit_miss_e_ttl() -> None:
    cache = ResponseCache(ttl_seconds=0.05)
    key = cache.make_key("p", model="m", system="s")
    assert cache.get(key) is None
    cache.set(key, "corpo")
    assert cache.get(key) == "corpo"
    time.sleep(0.06)
    assert cache.get(key) is None


def test_cache_ttl_zero_desliga() -> None:
    cache = ResponseCache(ttl_seconds=0)
    key = cache.make_key("p", model="m", system="s")
    cache.set(key, "corpo")
    assert cache.get(key) is None


def test_motor_usa_cache_na_nuvem() -> None:
    cache = ResponseCache(ttl_seconds=60)
    ollama = FakeOllama()
    cloud = FakeCloud(text="primeira")
    engine = HybridEngine(_config(), ollama, cloud, cache=cache)

    first = engine.reply("pensa mais sobre cache")
    assert first.text == "primeira"
    assert len(cloud.calls) == 1

    cloud.text = "segunda"
    second = engine.reply("pensa mais sobre cache")
    assert second.text == "primeira"
    assert second.model == "openrouter/free"
    assert len(cloud.calls) == 1


def test_cache_atualiza_sem_expulsar_outra_chave() -> None:
    cache = ResponseCache(ttl_seconds=60, max_entries=2)
    cache.set("a", "1")
    cache.set("b", "2")
    cache.set("b", "3")
    assert cache.get("a") == "1"
    assert cache.get("b") == "3"


def test_cache_em_disco_sobrevive_outro_objeto(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    cache = ResponseCache(ttl_seconds=60, path=path)
    key = cache.make_key("p", model="m", system="s")
    cache.set(key, "corpo")
    again = ResponseCache(ttl_seconds=60, path=path)
    assert again.get(key) == "corpo"
    assert path.stat().st_mode & 0o777 == 0o600


def test_motor_reusa_resposta_local() -> None:
    cache = ResponseCache(ttl_seconds=60)
    ollama = FakeOllama(text="uma vez")
    cloud = FakeCloud()
    engine = HybridEngine(_config(cloud_api_key=""), ollama, cloud, cache=cache)
    assert engine.reply("explica lista").text == "uma vez"
    ollama.text = "outra"
    assert engine.reply("explica lista").text == "uma vez"
    assert len(ollama.calls) == 1
    assert cloud.calls == []


def test_cache_de_nuvem_ignora_teto(tmp_path: Path) -> None:
    log_path = tmp_path / "usage.jsonl"
    cache = ResponseCache(ttl_seconds=60)
    cloud = FakeCloud(text="primeira")
    budget = CloudBudget(
        cloud_mode="ask",
        log_path=log_path,
        monthly_token_limit=200_000,
        warn_token_limit=150_000,
        require_confirm=False,
        allow_no_tty=True,
    )
    engine = HybridEngine(
        _config(),
        FakeOllama(),
        cloud,
        cache=cache,
        budget=budget,
        confirm_fn=lambda _msg: False,
    )
    assert engine.reply("pensa mais sobre cache").text == "primeira"
    log_path.write_text(
        json.dumps(
            {
                "timestamp": time.time(),
                "provider": "openrouter",
                "model": "m",
                "purpose": "test",
                "input_tokens_estimate": 500_000,
                "output_tokens_estimate": 1,
                "result": EVENT_COMPLETED,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    engine.budget = CloudBudget(
        cloud_mode="ask",
        log_path=log_path,
        monthly_token_limit=10,
        warn_token_limit=5,
        require_confirm=False,
        allow_no_tty=True,
    )
    cloud.text = "segunda"
    second = engine.reply("pensa mais sobre cache")
    assert second.text == "primeira"
    assert second.provider == "cloud"
    assert len(cloud.calls) == 1


def test_teto_mensal_degrada_para_local(tmp_path: Path) -> None:
    log_path = tmp_path / "usage.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "timestamp": time.time(),
                "provider": "openrouter",
                "model": "m",
                "purpose": "test",
                "input_tokens_estimate": 500_000,
                "output_tokens_estimate": 1,
                "result": EVENT_COMPLETED,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    budget = CloudBudget(
        cloud_mode="ask",
        log_path=log_path,
        monthly_token_limit=10,
        warn_token_limit=5,
        require_confirm=False,
        allow_no_tty=True,
    )
    ollama = FakeOllama(text="local-ok")
    cloud = FakeCloud(text="nuvem")
    engine = HybridEngine(
        _config(),
        ollama,
        cloud,
        cache=ResponseCache(ttl_seconds=0),
        budget=budget,
        confirm_fn=lambda _msg: True,
    )
    reply = engine.reply("pensa mais sobre orcamento")
    assert reply.provider == "local"
    assert reply.text == "local-ok"
    assert reply.notice is not None
    assert "Teto mensal" in reply.notice or "nuvem" in reply.notice.casefold()
    assert cloud.calls == []
    assert len(ollama.calls) == 1


def test_engine_from_env_cache_em_disco(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("YBY_CACHE_PATH", str(tmp_path / "c.json"))
    monkeypatch.setenv("YBY_CACHE_TTL_SECONDS", "15")
    engine = engine_from_env(confirm_fn=lambda _msg: False)
    assert engine.cache.path == tmp_path / "c.json"

    monkeypatch.setenv("YBY_CACHE_PATH", "memory")
    engine = engine_from_env(confirm_fn=lambda _msg: False)
    assert engine.cache.path is None

    monkeypatch.setenv("YBY_CACHE_TTL_SECONDS", "0")
    monkeypatch.setenv("YBY_CACHE_PATH", str(tmp_path / "c.json"))
    engine = engine_from_env(confirm_fn=lambda _msg: False)
    assert engine.cache.path is None
