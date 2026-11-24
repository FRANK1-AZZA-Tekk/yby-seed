"""Tokens informados pela nuvem (usage) sem alterar orçamento."""

from __future__ import annotations

import json

import pytest

from src.engine.budget import CloudBudget
from src.engine.cache import ResponseCache
from src.engine.cloud_usage_log import EVENT_COMPLETED
from src.engine.cloud_usage_log import CloudUsageLog
from src.engine.hybrid import HybridEngine
from src.engine.providers import (
    CascadingCloudProvider,
    CloudProvider,
    extract_reported_usage,
    reported_token_count,
)
from tests.test_cloud_usage_log import _Resp, _Session
from tests.test_engine import FakeOllama, _config


def test_reported_token_count_rejeita_bool_e_negativo() -> None:
    assert reported_token_count(True) is None
    assert reported_token_count(False) is None
    assert reported_token_count(-1) is None
    assert reported_token_count("3") is None
    assert reported_token_count(0) == 0
    assert reported_token_count(42) == 42


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        (None, (None, None)),
        ({}, (None, None)),
        ({"prompt_tokens": 10, "completion_tokens": 5}, (10, 5)),
        ({"prompt_tokens": 0, "completion_tokens": 0}, (0, 0)),
        ({"prompt_tokens": 7}, (7, None)),
        ({"completion_tokens": 3}, (None, 3)),
        ({"prompt_tokens": True, "completion_tokens": 2}, (None, 2)),
        ({"prompt_tokens": "x", "completion_tokens": 1}, (None, 1)),
    ],
)
def test_extract_reported_usage(usage: object | None, expected: tuple[int | None, int | None]) -> None:
    payload: dict[str, object] = {"choices": [{"message": {"content": "ok"}}]}
    if usage is not None:
        payload["usage"] = usage
    assert extract_reported_usage(payload) == expected


def test_complete_ainda_devolve_so_texto() -> None:
    session = _Session(
        _Resp(
            200,
            {
                "choices": [{"message": {"content": "resposta"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 4},
            },
        )
    )
    provider = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="k",
        timeout=1,
        session=session,
    )
    assert provider.complete("oi", model="m", system="s") == "resposta"
    assert len(session.posts) == 1  # type: ignore[attr-defined]


def test_complete_detail_uma_chamada_http() -> None:
    session = _Session(
        _Resp(
            200,
            {
                "choices": [{"message": {"content": "resposta"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 4},
            },
        )
    )
    provider = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="k",
        timeout=1,
        session=session,
    )
    detail = provider.complete_detail("oi", model="m", system="s")
    assert detail.text == "resposta"
    assert detail.input_tokens_reported == 11
    assert detail.output_tokens_reported == 4
    assert len(session.posts) == 1  # type: ignore[attr-defined]


def test_usage_invalido_nao_impede_texto() -> None:
    session = _Session(
        _Resp(
            200,
            {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": "nope", "completion_tokens": False},
            },
        )
    )
    detail = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="k",
        timeout=1,
        session=session,
    ).complete_detail("oi", model="m", system="s")
    assert detail.text == "ok"
    assert detail.input_tokens_reported is None
    assert detail.output_tokens_reported is None


def test_cloud_completed_grava_tokens_reportados(tmp_path) -> None:
    session = _Session(
        _Resp(
            200,
            {
                "choices": [{"message": {"content": "OK"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 9},
            },
        )
    )
    log = CloudUsageLog(tmp_path / "cloud_usage.jsonl")
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "ask",
            "YBY_CLOUD_LOG_PATH": str(log.path),
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "999999",
        }
    )
    chain = CascadingCloudProvider(
        CloudProvider(
            "https://openrouter.ai/api/v1",
            api_key="k",
            timeout=1,
            session=session,
        ),
        primary_model="openrouter/free",
    )
    engine = HybridEngine(
        _config(cache_ttl_seconds=0),
        FakeOllama(),
        chain,
        cloud_chain=chain,
        cache=ResponseCache(ttl_seconds=0),
        cloud_log=log,
        budget=budget,
        confirm_fn=lambda _: True,
        has_tty_fn=lambda: True,
    )
    reply = engine.reply("oi", explicit_heavy=True)
    assert reply.provider == "cloud"

    completed = [
        json.loads(line)
        for line in log.path.read_text(encoding="utf-8").strip().splitlines()
        if json.loads(line)["result"] == EVENT_COMPLETED
    ]
    assert len(completed) == 1
    event = completed[0]
    assert event["input_tokens_estimate"] >= 1
    assert event["output_tokens_estimate"] >= 1
    assert event["input_tokens_reported"] == 100
    assert event["output_tokens_reported"] == 9
    assert "usage" not in log.path.read_text(encoding="utf-8")


def test_cache_nao_grava_novo_completed_com_reported(tmp_path) -> None:
    session = _Session(
        _Resp(
            200,
            {
                "choices": [{"message": {"content": "cached-body"}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 5},
            },
        )
    )
    log = CloudUsageLog(tmp_path / "cloud_usage.jsonl")
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "ask",
            "YBY_CLOUD_LOG_PATH": str(log.path),
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "200000",
        }
    )
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
        _config(cache_ttl_seconds=90),
        FakeOllama(),
        chain,
        cloud_chain=chain,
        cache=ResponseCache(ttl_seconds=90),
        cloud_log=log,
        budget=budget,
        confirm_fn=lambda _: True,
        has_tty_fn=lambda: True,
    )

    first = engine.reply("oi", explicit_heavy=True)
    assert first.provider == "cloud"
    assert session.posts  # type: ignore[attr-defined]

    posts_after_first = len(session.posts)  # type: ignore[attr-defined]
    second = engine.reply("oi", explicit_heavy=True)
    assert second.provider == "cloud"
    assert second.text == "cached-body"
    assert len(session.posts) == posts_after_first  # type: ignore[attr-defined]

    completed = [
        json.loads(line)
        for line in log.path.read_text(encoding="utf-8").strip().splitlines()
        if json.loads(line)["result"] == EVENT_COMPLETED
    ]
    assert len(completed) == 1
    assert completed[0]["input_tokens_reported"] == 50


def test_orcamento_ignora_tokens_reportados(tmp_path) -> None:
    """Orçamento continua somando só *_estimate (comportamento inalterado nesta rodada)."""

    session = _Session(
        _Resp(
            200,
            {
                "choices": [{"message": {"content": "x"}}],
                "usage": {"prompt_tokens": 999_999, "completion_tokens": 999_999},
            },
        )
    )
    log = CloudUsageLog(tmp_path / "cloud_usage.jsonl")
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "ask",
            "YBY_CLOUD_LOG_PATH": str(log.path),
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "500",
            "YBY_CLOUD_DAILY_TOKEN_LIMIT": "500",
        }
    )
    chain = CascadingCloudProvider(
        CloudProvider(
            "https://openrouter.ai/api/v1",
            api_key="k",
            timeout=1,
            session=session,
        ),
        primary_model="openrouter/free",
    )
    engine = HybridEngine(
        _config(cache_ttl_seconds=0),
        FakeOllama(),
        chain,
        cloud_chain=chain,
        cache=ResponseCache(ttl_seconds=0),
        cloud_log=log,
        budget=budget,
        confirm_fn=lambda _: True,
        has_tty_fn=lambda: True,
    )
    reply = engine.reply("oi", explicit_heavy=True)
    assert reply.provider == "cloud"
    second = engine.reply("outro", explicit_heavy=True)
    assert second.provider == "cloud"


class _LegacyCloudClient:
    """Só `complete()` — sem `complete_detail` (contrato CloudClient mínimo)."""

    def __init__(self, text: str = "legado") -> None:
        self.text = text
        self.calls = 0

    def has_credentials(self) -> bool:
        return True

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        self.calls += 1
        return self.text


def _engine_sem_cascata(
    tmp_path,
    cloud,
    *,
    cache_ttl: float = 0,
    confirm: bool = True,
) -> tuple[HybridEngine, CloudUsageLog]:
    log = CloudUsageLog(tmp_path / "cloud_usage.jsonl")
    budget = CloudBudget.from_env(
        {
            "YBY_CLOUD_MODE": "ask",
            "YBY_CLOUD_LOG_PATH": str(log.path),
            "YBY_CLOUD_REQUIRE_CONFIRM": "0",
            "YBY_CLOUD_MONTHLY_TOKEN_LIMIT": "200000",
        }
    )
    engine = HybridEngine(
        _config(cache_ttl_seconds=cache_ttl),
        FakeOllama(),
        cloud,  # type: ignore[arg-type]
        cloud_chain=None,
        cache=ResponseCache(ttl_seconds=cache_ttl),
        cloud_log=log,
        budget=budget,
        confirm_fn=lambda _: confirm,
        has_tty_fn=lambda: True,
    )
    return engine, log


def test_sem_cascata_provider_grava_reported(tmp_path) -> None:
    session = _Session(
        _Resp(
            200,
            {
                "choices": [{"message": {"content": "direto"}}],
                "usage": {"prompt_tokens": 31, "completion_tokens": 6},
            },
        )
    )
    provider = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="k",
        timeout=1,
        session=session,
    )
    engine, log = _engine_sem_cascata(tmp_path, provider)
    reply = engine.reply("oi", explicit_heavy=True)
    assert reply.provider == "cloud"
    assert reply.text == "direto"
    assert len(session.posts) == 1  # type: ignore[attr-defined]

    completed = [
        json.loads(line)
        for line in log.path.read_text(encoding="utf-8").strip().splitlines()
        if json.loads(line)["result"] == EVENT_COMPLETED
    ]
    assert completed[0]["input_tokens_reported"] == 31
    assert completed[0]["output_tokens_reported"] == 6


def test_sem_cascata_legado_sem_metadados(tmp_path) -> None:
    legacy = _LegacyCloudClient()
    engine, log = _engine_sem_cascata(tmp_path, legacy)
    reply = engine.reply("oi", explicit_heavy=True)
    assert reply.provider == "cloud"
    assert legacy.calls == 1
    body = log.path.read_text(encoding="utf-8")
    assert "input_tokens_reported" not in body


def test_sem_cascata_erro_http_unica_tentativa_local(tmp_path) -> None:
    session = _Session(_Resp(400, {"error": {"message": "rejeitado"}}))
    provider = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="k",
        timeout=1,
        session=session,
    )
    engine, _log = _engine_sem_cascata(tmp_path, provider)
    reply = engine.reply("oi", explicit_heavy=True)
    # D12: falha de nuvem degrada para local; não dispara segunda chamada HTTP no motor.
    assert reply.provider == "local"
    assert len(session.posts) == 1  # type: ignore[attr-defined]


def test_sem_cascata_cache_sem_novo_completed(tmp_path) -> None:
    session = _Session(
        _Resp(
            200,
            {
                "choices": [{"message": {"content": "hit"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 2},
            },
        )
    )
    provider = CloudProvider(
        "https://openrouter.ai/api/v1",
        api_key="k",
        timeout=2,
        session=session,
    )
    engine, log = _engine_sem_cascata(tmp_path, provider, cache_ttl=90)
    first = engine.reply("oi", explicit_heavy=True)
    assert first.text == "hit"
    posts_after = len(session.posts)  # type: ignore[attr-defined]
    second = engine.reply("oi", explicit_heavy=True)
    assert second.text == "hit"
    assert len(session.posts) == posts_after  # type: ignore[attr-defined]

    completed = [
        json.loads(line)
        for line in log.path.read_text(encoding="utf-8").strip().splitlines()
        if json.loads(line)["result"] == EVENT_COMPLETED
    ]
    assert len(completed) == 1
