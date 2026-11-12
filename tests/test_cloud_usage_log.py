"""Log JSONL e integração híbrida (issue #42)."""

from __future__ import annotations

import json
import os
import stat

import pytest

from src.engine.budget import CloudBudget
from src.engine.cloud_usage_log import (
    CloudUsageLog,
    EVENT_CANCELLED,
    EVENT_COMPLETED,
    EVENT_BLOCKED_LOCAL_ONLY,
    utc_timestamp,
)
from src.engine.cache import ResponseCache
from src.engine.hybrid import HybridEngine
from src.engine.providers import CascadingCloudProvider, CloudProvider, ProviderError
from tests.test_engine import FakeCloud, FakeOllama, _config


class _Resp:
    def __init__(self, status: int, payload: object) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> object:
        return self._payload


class _Session:
    def __init__(self, response: _Resp) -> None:
        self.response = response
        self.posts: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> _Resp:
        self.posts.append({"url": url, **kwargs})
        return self.response


def _engine(
    tmp_path,
    *,
    confirm_fn,
    ollama: FakeOllama | None = None,
    cloud_key: str = "or-key",
    cloud_error: Exception | None = None,
) -> tuple[HybridEngine, CloudUsageLog]:
    log = CloudUsageLog(tmp_path / "cloud_usage.jsonl")
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "ask",
            "YBY_CLOUD_LOG_PATH": str(log.path),
            "YBY_CLOUD_REQUIRE_CONFIRM": "1",
            "YBY_CLOUD_ALLOW_NO_TTY": "1",
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "200000",
        }
    )
    ollama = ollama or FakeOllama()
    if cloud_error:
        cloud: CascadingCloudProvider | FakeCloud = CascadingCloudProvider(
            CloudProvider(
                "https://openrouter.ai/api/v1",
                api_key=cloud_key,
                timeout=2,
                session=_Session(_Resp(503, {"error": "busy"})),
            ),
            primary_model="openrouter/free",
        )
    else:
        cloud = FakeCloud(api_key=cloud_key)
    engine = HybridEngine(
        _config(cache_ttl_seconds=0),
        ollama,
        cloud,  # type: ignore[arg-type]
        cloud_chain=cloud if isinstance(cloud, CascadingCloudProvider) else None,
        cache=ResponseCache(ttl_seconds=0),
        cloud_log=log,
        budget=budget,
        confirm_fn=confirm_fn,
        has_tty_fn=lambda: True,
    )
    return engine, log


def test_rota_local_sem_evento_nuvem(tmp_path) -> None:
    engine, log = _engine(tmp_path, confirm_fn=lambda _: True)
    reply = engine.reply("explica uma lista")
    assert reply.provider == "local"
    assert not log.path.exists()


def test_heavy_confirmacao_negada(tmp_path) -> None:
    engine, log = _engine(tmp_path, confirm_fn=lambda _: False)
    reply = engine.reply("oi", explicit_heavy=True)
    assert reply.provider == "none"
    assert log.path.is_file()
    lines = log.path.read_text(encoding="utf-8").strip().splitlines()
    assert any(json.loads(line)["result"] == EVENT_CANCELLED for line in lines)


def test_heavy_confirmacao_positiva_registra_jsonl(tmp_path) -> None:
    engine, log = _engine(tmp_path, confirm_fn=lambda _: True)
    reply = engine.reply("oi", explicit_heavy=True)
    assert reply.provider == "cloud"
    line = json.loads(log.path.read_text(encoding="utf-8").strip().splitlines()[-1])
    for key in (
        "timestamp",
        "provider",
        "model",
        "purpose",
        "input_tokens_estimate",
        "output_tokens_estimate",
        "result",
    ):
        assert key in line
    assert line["result"] == EVENT_COMPLETED
    assert "sk-" not in log.path.read_text(encoding="utf-8")


def test_local_only_sem_http(tmp_path) -> None:
    log = CloudUsageLog(tmp_path / "cloud_usage.jsonl")
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "local_only",
            "YBY_CLOUD_LOG_PATH": str(log.path),
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
        }
    )
    session = _Session(_Resp(200, {"choices": [{"message": {"content": "x"}}]}))
    chain = CascadingCloudProvider(
        CloudProvider(
            "https://openrouter.ai/api/v1",
            api_key="k",
            timeout=2,
            session=session,
        ),
        primary_model="openrouter/free",
    )
    engine = HybridEngine(
        _config(),
        FakeOllama(),
        chain,
        cloud_chain=chain,
        cache=ResponseCache(ttl_seconds=0),
        cloud_log=log,
        budget=budget,
        confirm_fn=lambda _: True,
        has_tty_fn=lambda: True,
    )
    reply = engine.reply("pensa mais", explicit_heavy=False)
    assert reply.provider == "none"
    assert session.posts == []
    blocked = json.loads(log.path.read_text(encoding="utf-8").strip())
    assert blocked["result"] == EVENT_BLOCKED_LOCAL_ONLY


def test_ollama_falha_exige_confirmacao(tmp_path) -> None:
    asks = {"n": 0}

    def confirm(_: str) -> bool:
        asks["n"] += 1
        return False

    engine, log = _engine(
        tmp_path,
        confirm_fn=confirm,
        ollama=FakeOllama(error=ProviderError("down")),
        cloud_error=ProviderError("unused"),
    )
    reply = engine.reply("oi")
    assert asks["n"] == 1
    assert reply.provider == "none"
    assert json.loads(log.path.read_text(encoding="utf-8").strip().splitlines()[-1])[
        "result"
    ] == EVENT_CANCELLED


def test_log_perm_0600(tmp_path) -> None:
    log = CloudUsageLog(tmp_path / "cloud_usage.jsonl")
    log.append(
        {
            "timestamp": 1.0,
            "provider": "openrouter",
            "model": "m",
            "purpose": "t",
            "input_tokens_estimate": 1,
            "output_tokens_estimate": 0,
            "result": "cloud_requested",
        }
    )
    mode = stat.S_IMODE(os.stat(log.path).st_mode)
    assert mode == 0o600


def test_aviso_orcamento_no_stderr_antes_confirmacao(tmp_path) -> None:
    log = CloudUsageLog(tmp_path / "cloud_usage.jsonl")
    log.append(
        {
            "timestamp": utc_timestamp(),
            "provider": "openrouter",
            "model": "m",
            "purpose": "seed",
            "input_tokens_estimate": 100_000,
            "output_tokens_estimate": 60_000,
            "result": EVENT_COMPLETED,
        }
    )
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "ask",
            "YBY_CLOUD_LOG_PATH": str(log.path),
            "YBY_CLOUD_REQUIRE_CONFIRM": "1",
            "YBY_CLOUD_ALLOW_NO_TTY": "1",
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "200000",
            "YBY_CLOUD_WARN_TOKEN_LIMIT": "150000",
        }
    )
    order: list[str] = []

    def confirm(_msg: str) -> bool:
        order.append("confirm")
        return True

    engine = HybridEngine(
        _config(cache_ttl_seconds=0),
        FakeOllama(),
        FakeCloud(api_key="k"),
        cache=ResponseCache(ttl_seconds=0),
        cloud_log=log,
        budget=budget,
        confirm_fn=confirm,
        has_tty_fn=lambda: True,
        budget_warn_fn=lambda msg: order.append(f"warn:{msg}"),
    )
    reply = engine.reply("oi", explicit_heavy=True)
    assert reply.provider == "cloud"
    assert len(order) >= 2
    assert order[0].startswith("warn:Aviso:")
    assert order[1] == "confirm"


def test_log_rejeita_prompt_no_evento(tmp_path) -> None:
    log = CloudUsageLog(tmp_path / "cloud_usage.jsonl")
    with pytest.raises(ValueError, match="proibido"):
        log.append(
            {
                "timestamp": 1.0,
                "provider": "openrouter",
                "model": "m",
                "purpose": "t",
                "input_tokens_estimate": 1,
                "output_tokens_estimate": 0,
                "result": "cloud_requested",
                "prompt": "segredo",
            }
        )
