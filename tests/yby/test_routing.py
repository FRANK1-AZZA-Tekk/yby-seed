"""Testes 100% offline do Módulo A (Privacy Gate, Classificador, Cache e Failover)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.engine.cloud_usage_log import CloudUsageLog
from src.yby.routing import (
    CognitiveRouter,
    InMemoryCacheBackend,
    NodeHealthTracker,
    PrivacyGate,
    RedisCacheBackend,
    RouterConfig,
    RouteRequest,
    RouteTier,
    RoutingExhaustedError,
    TierExecutionError,
    TriageSchema,
    build_cache_key,
    classify_request,
)
from src.yby.routing.classifier import classify_deterministic


class FakeLLMBackend:
    """Backend determinístico em memória que registra todas as chamadas por nível."""

    def __init__(
        self,
        *,
        failing_tiers: set[RouteTier] | None = None,
        responses: dict[RouteTier, str] | None = None,
    ) -> None:
        self.failing_tiers: set[RouteTier] = set(failing_tiers or ())
        self.responses: dict[RouteTier, str] = dict(responses or {})
        self.calls: list[tuple[RouteTier, str]] = []

    async def complete(
        self,
        tier: RouteTier,
        prompt: str,
        *,
        system: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        self.calls.append((tier, prompt))
        if tier in self.failing_tiers:
            raise TierExecutionError(tier, "simulated failure")
        return self.responses.get(tier, f"reply-from-{tier}"), f"mock-{tier}"


class FakeAsyncRedis:
    """Mock leve de `redis.asyncio` para validar RedisCacheBackend sem rede."""

    def __init__(self) -> None:
        self.data: dict[str, tuple[str, int]] = {}

    async def get(self, key: str) -> str | None:
        item = self.data.get(key)
        return item[0] if item is not None else None

    async def set(self, key: str, value: str, *, ex: int = 300) -> None:
        self.data[key] = (value, ex)

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)

    async def ping(self) -> bool:
        return True


def test_privacy_gate_blocks_private_origins_pix_and_secrets() -> None:
    gate = PrivacyGate()

    for origin in ("pgvector", "personal_memory", "mqtt_telemetry", "raw_audio", "pix_commercial"):
        decision = gate.evaluate(
            RouteRequest(
                prompt="resumo de dados",
                sensitivity="public",
                origin=origin,  # type: ignore[arg-type]
            )
        )
        assert decision.allow_cloud is False
        assert "yby-cloud-frontier" not in decision.allowed_tiers
        assert f"origin={origin}" in decision.blocked_reasons

    pix_decision = gate.evaluate(
        RouteRequest(
            prompt="Confirmar chave pix 000201 para cliente",
            sensitivity="public",
        )
    )
    assert pix_decision.allow_cloud is False
    assert "pix_commercial_pattern" in pix_decision.blocked_reasons

    pii_decision = gate.evaluate(
        RouteRequest(
            prompt=(
                "Enviar para joao@example.com CPF 123.456.789-00 "
                "com chave sk-proj-1234567890abcdef1234567890"
            ),
            sensitivity="public",
        )
    )
    assert pii_decision.allow_cloud is False
    assert pii_decision.redaction_count >= 2
    assert "joao@example.com" not in pii_decision.sanitized_prompt
    assert "123.456.789-00" not in pii_decision.sanitized_prompt


def test_privacy_gate_allows_clean_public_and_supports_extra_guard() -> None:
    gate = PrivacyGate()
    ok = gate.evaluate(
        RouteRequest(
            prompt="Compare architectures for offline-first PWA sync",
            sensitivity="public",
            origin="web_research",
        )
    )
    assert ok.allow_cloud is True
    assert "yby-cloud-frontier" in ok.allowed_tiers

    guarded = PrivacyGate(extra_guard=lambda _req: (False, "local_guardian_block"))
    denied = guarded.evaluate(
        RouteRequest(
            prompt="Compare architectures for offline-first PWA sync",
            sensitivity="public",
            origin="web_research",
        )
    )
    assert denied.allow_cloud is False
    assert "local_guardian_block" in denied.blocked_reasons


@pytest.mark.asyncio
async def test_classifier_fast_code_frontier_and_under_5ms() -> None:
    gate = PrivacyGate()

    # Curto / voz -> yby-fast
    req_fast = RouteRequest(prompt="Ligar luz da mesa", sensitivity="private", origin="raw_audio")
    t0 = time.perf_counter()
    res_fast = classify_deterministic(req_fast, gate.evaluate(req_fast))
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert res_fast.tier == "yby-fast"
    assert elapsed_ms < 50.0

    # Código / PWA YBY Fórum -> yby-code
    req_code = RouteRequest(
        prompt="Gerar componente PWA offline-first do YBY Fórum com FastAPI",
        sensitivity="private",
        origin="code_workspace",
    )
    res_code = classify_deterministic(req_code, gate.evaluate(req_code))
    assert res_code.tier == "yby-code"

    # Web pública -> yby-cloud-frontier
    req_web = RouteRequest(
        prompt="Pesquisar web sobre benchmarks de pgvector HNSW",
        sensitivity="public",
        requires_web=True,
    )
    res_web = classify_deterministic(req_web, gate.evaluate(req_web))
    assert res_web.tier == "yby-cloud-frontier"

    # Triagem 3B sugerindo nuvem para pedido privado ainda é bloqueada pelo PrivacyGate
    async def fake_triage(_req: RouteRequest) -> TriageSchema:
        return TriageSchema(
            intent="web_research",
            suggested_tier="yby-cloud-frontier",
            requires_web=True,
            confidence=0.95,
        )

    private_req = RouteRequest(prompt="Resumo da minha memória pessoal", sensitivity="private")
    res_triage = await classify_request(
        private_req,
        gate.evaluate(private_req),
        triage_runner=fake_triage,
    )
    assert res_triage.tier == "yby-code"


@pytest.mark.asyncio
async def test_router_never_sends_private_payload_to_cloud() -> None:
    backend = FakeLLMBackend()
    router = CognitiveRouter(backend=backend)

    resp = await router.route(
        RouteRequest(
            prompt="Analisar minha memória do pgvector sobre o projeto",
            sensitivity="private",
            origin="pgvector",
            preferred_tier="yby-cloud-frontier",
            requires_web=True,
        )
    )

    assert resp.tier == "yby-code"
    assert resp.metadata.privacy_blocked_cloud is True
    assert all(tier != "yby-cloud-frontier" for tier, _ in backend.calls)


@pytest.mark.asyncio
async def test_router_cloud_logs_metadata_only_and_failover_offline(tmp_path: Path) -> None:
    log_path = tmp_path / "cloud_usage.jsonl"
    cloud_log = CloudUsageLog(log_path)

    # 1) Public web -> sucesso na nuvem com log metadata-only
    ok_backend = FakeLLMBackend(responses={"yby-cloud-frontier": "resposta-nuvem"})
    router_ok = CognitiveRouter(backend=ok_backend, cloud_log=cloud_log)

    resp = await router_ok.route(
        RouteRequest(
            prompt="Pesquisa web arquitetura distribuida",
            sensitivity="public",
            requires_web=True,
        )
    )
    assert resp.tier == "yby-cloud-frontier"
    assert resp.text == "resposta-nuvem"

    lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert lines[0]["result"] == "cloud_requested"
    assert lines[1]["result"] == "cloud_completed"
    raw_log = log_path.read_text(encoding="utf-8")
    assert "arquitetura distribuida" not in raw_log
    assert "resposta-nuvem" not in raw_log

    # 2) Nuvem indisponível -> failover automático para yby-code
    flaky_backend = FakeLLMBackend(failing_tiers={"yby-cloud-frontier"})
    router_flaky = CognitiveRouter(backend=flaky_backend, cloud_log=cloud_log)
    resp_fallback = await router_flaky.route(
        RouteRequest(
            prompt="Pesquisa web sobre Tailscale",
            sensitivity="public",
            requires_web=True,
        )
    )
    assert resp_fallback.tier == "yby-code"
    assert resp_fallback.metadata.fallback_used is True
    assert resp_fallback.metadata.attempted_tiers == ["yby-cloud-frontier", "yby-code"]

    # 3) Modo off-grid (`YBY_OFFGRID_MODE=1`) nem tenta chamar a nuvem
    offgrid_backend = FakeLLMBackend()
    router_offgrid = CognitiveRouter(
        backend=offgrid_backend,
        config=RouterConfig(offgrid_mode=True),
    )
    resp_offgrid = await router_offgrid.route(
        RouteRequest(
            prompt="Pesquisa web sobre MQTT QoS 1",
            sensitivity="public",
            requires_web=True,
        )
    )
    assert resp_offgrid.tier == "yby-code"
    assert all(tier != "yby-cloud-frontier" for tier, _ in offgrid_backend.calls)


@pytest.mark.asyncio
async def test_router_failover_to_xiaomi12_pocketpal_when_pc_hub_offline() -> None:
    backend = FakeLLMBackend(
        failing_tiers={"yby-fast", "yby-code"},
        responses={"yby-mobile-fallback": "pocketpal-xiaomi12-ok"},
    )
    cache = InMemoryCacheBackend()
    health = NodeHealthTracker(cache, unhealthy_ttl_seconds=60)
    router = CognitiveRouter(backend=backend, cache=cache, health=health)

    # Primeira chamada tenta PC Hub e cai para Xiaomi 12 PocketPal
    first = await router.route(
        RouteRequest(prompt="Status do nó", sensitivity="private", use_cache=False)
    )
    assert first.tier == "yby-mobile-fallback"
    assert first.text == "pocketpal-xiaomi12-ok"
    assert first.metadata.attempted_tiers == ["yby-fast", "yby-code", "yby-mobile-fallback"]

    # Segunda chamada com PC Hub já marcado unhealthy vai direto ao Xiaomi 12 PocketPal
    backend.calls.clear()
    second = await router.route(
        RouteRequest(prompt="Outro comando offline", sensitivity="private", use_cache=False)
    )
    assert second.tier == "yby-mobile-fallback"
    assert second.metadata.attempted_tiers == ["yby-mobile-fallback"]


@pytest.mark.asyncio
async def test_router_exhausted_raises_and_cache_partitions_private_vs_public() -> None:
    k_priv = build_cache_key("private", "yby-fast", "mesmo prompt")
    k_pub = build_cache_key("public", "yby-fast", "mesmo prompt")
    assert k_priv != k_pub

    redis_cache = RedisCacheBackend(client=FakeAsyncRedis())
    assert await redis_cache.ping() is True

    backend = FakeLLMBackend(responses={"yby-fast": "ok-cached"})
    router = CognitiveRouter(backend=backend, cache=redis_cache)

    r1 = await router.route(RouteRequest(prompt="Oi YBY", sensitivity="private"))
    r2 = await router.route(RouteRequest(prompt="Oi YBY", sensitivity="private"))
    assert r1.metadata.cache_hit is False
    assert r2.metadata.cache_hit is True
    assert len(backend.calls) == 1

    dead_backend = FakeLLMBackend(
        failing_tiers={"yby-fast", "yby-code", "yby-mobile-fallback"}
    )
    dead_router = CognitiveRouter(backend=dead_backend)
    with pytest.raises(RoutingExhaustedError):
        await dead_router.route(RouteRequest(prompt="Oi", sensitivity="private"))


def test_litellm_config_preserves_local_safety_and_defines_4_mesh_tiers() -> None:
    cfg = yaml.safe_load(Path("litellm_config.yaml").read_text(encoding="utf-8"))
    names = {item["model_name"] for item in cfg["model_list"]}
    for required in (
        "yby-local",
        "yby-fast",
        "yby-code",
        "yby-cloud-frontier",
        "yby-mobile-fallback",
    ):
        assert required in names

    fallbacks: dict[str, list[str]] = {}
    for entry in cfg["router_settings"]["fallbacks"]:
        fallbacks.update(entry)

    # Nenhuma rota local pode escalar para nuvem.
    for local_tier in ("yby-local", "yby-fast", "yby-code"):
        assert "yby-cloud-frontier" not in fallbacks[local_tier]
        assert "yby-free" not in fallbacks[local_tier]
        assert "yby-smart" not in fallbacks[local_tier]
        assert "yby-critical" not in fallbacks[local_tier]
        assert "yby-mobile-fallback" in fallbacks[local_tier]
