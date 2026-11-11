"""Cache de respostas e limite de contexto."""

from __future__ import annotations

import time

from src.engine.cache import ResponseCache
from src.engine.context import trim_context
from src.engine.hybrid import HybridEngine
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
