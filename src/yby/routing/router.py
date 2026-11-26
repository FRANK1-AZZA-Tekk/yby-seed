"""CognitiveRouter assíncrono com cascata local-first, Privacy Gate e failover PocketPal."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import httpx

from src.engine.cloud_usage_log import (
    EVENT_COMPLETED,
    EVENT_FAILED,
    EVENT_REQUESTED,
    CloudUsageLog,
    utc_timestamp,
)
from src.yby.routing.cache import (
    CacheBackend,
    InMemoryCacheBackend,
    NodeHealthTracker,
    build_cache_key,
)
from src.yby.routing.classifier import TriageRunner, classify_request
from src.yby.routing.privacy_gate import PrivacyGate
from src.yby.routing.schemas import (
    RouteMetadata,
    RouteRequest,
    RouteResponse,
    RouteTier,
)

PC_HUB_NODE = "desktop-yby"
MOBILE_FALLBACK_NODE = "xiaomi12"


class TierExecutionError(RuntimeError):
    """Erro recuperável ao chamar um nível específico da cascata."""

    def __init__(self, tier: RouteTier, message: str) -> None:
        super().__init__(f"[{tier}] {message}")
        self.tier = tier
        self.detail = message


class RoutingExhaustedError(RuntimeError):
    """Todos os níveis elegíveis da cascata falharam."""

    def __init__(self, attempts: list[tuple[RouteTier, str]]) -> None:
        summary = "; ".join(f"{tier}: {err}" for tier, err in attempts)
        super().__init__(f"Todos os níveis de roteamento falharam: {summary}")
        self.attempts = attempts


@dataclass(frozen=True)
class RouterConfig:
    """Configuração de endpoints e modelos dos 4 níveis (sem segredos no código)."""

    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    fast_model: str = "qwen2.5-coder:3b"
    code_model: str = "qwen2.5-coder:7b"
    cloud_base_url: str = "https://openrouter.ai/api/v1"
    cloud_model: str = "openrouter/free"
    cloud_api_key: str = ""
    pocketpal_base_url: str = "http://100.64.0.2:8080/v1"
    pocketpal_model: str = "qwen2.5-coder-3b-instruct"
    cache_ttl_seconds: int = 300
    request_timeout_seconds: float = 45.0
    offgrid_mode: bool = False

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> RouterConfig:
        source = environ if environ is not None else os.environ
        ollama_raw = (
            source.get("YBY_OLLAMA_BASE_URL")
            or source.get("OLLAMA_API_BASE")
            or "http://127.0.0.1:11434"
        ).strip().rstrip("/")
        ollama_v1 = ollama_raw if ollama_raw.endswith("/v1") else f"{ollama_raw}/v1"

        cloud_key = (
            source.get("YBY_CLOUD_API_KEY")
            or source.get("OPENROUTER_API_KEY")
            or ""
        ).strip()
        offgrid_raw = source.get("YBY_OFFGRID_MODE", "0").strip().casefold()
        offgrid = offgrid_raw in {"1", "true", "yes", "on"}

        ttl_raw = source.get("YBY_CACHE_TTL_SECONDS", "300").strip()
        ttl = int(ttl_raw) if ttl_raw else 300

        return cls(
            ollama_base_url=ollama_v1,
            fast_model=source.get("YBY_FAST_MODEL", "qwen2.5-coder:3b").strip()
            or "qwen2.5-coder:3b",
            code_model=source.get("YBY_CODE_MODEL", "qwen2.5-coder:7b").strip()
            or "qwen2.5-coder:7b",
            cloud_base_url=(
                source.get("YBY_CLOUD_BASE_URL", "https://openrouter.ai/api/v1").strip()
                or "https://openrouter.ai/api/v1"
            ).rstrip("/"),
            cloud_model=(
                source.get("YBY_CLOUD_FRONTIER_MODEL")
                or source.get("YBY_CLOUD_MODEL")
                or "openrouter/free"
            ).strip(),
            cloud_api_key=cloud_key,
            pocketpal_base_url=(
                source.get("YBY_POCKETPAL_BASE_URL", "http://100.64.0.2:8080/v1").strip()
                or "http://100.64.0.2:8080/v1"
            ).rstrip("/"),
            pocketpal_model=(
                source.get("YBY_POCKETPAL_MODEL", "qwen2.5-coder-3b-instruct").strip()
                or "qwen2.5-coder-3b-instruct"
            ),
            cache_ttl_seconds=max(1, ttl),
            offgrid_mode=offgrid,
        )


@runtime_checkable
class LLMBackend(Protocol):
    async def complete(
        self,
        tier: RouteTier,
        prompt: str,
        *,
        system: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, str]: ...


class OpenAICompatibleBackend:
    """Cliente HTTP assíncrono compatível com Ollama, OpenRouter e PocketPal (:8080/v1)."""

    def __init__(
        self,
        config: RouterConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._external_client = http_client

    def _endpoint_for(self, tier: RouteTier) -> tuple[str, str, dict[str, str]]:
        if tier == "yby-fast":
            return f"{self.config.ollama_base_url}/chat/completions", self.config.fast_model, {}
        if tier == "yby-code":
            return f"{self.config.ollama_base_url}/chat/completions", self.config.code_model, {}
        if tier == "yby-mobile-fallback":
            return (
                f"{self.config.pocketpal_base_url}/chat/completions",
                self.config.pocketpal_model,
                {},
            )
        headers: dict[str, str] = {}
        if self.config.cloud_api_key:
            headers["Authorization"] = f"Bearer {self.config.cloud_api_key}"
        return f"{self.config.cloud_base_url}/chat/completions", self.config.cloud_model, headers

    async def complete(
        self,
        tier: RouteTier,
        prompt: str,
        *,
        system: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        url, model, headers = self._endpoint_for(tier)
        if tier == "yby-cloud-frontier" and not self.config.cloud_api_key:
            raise TierExecutionError(tier, "chave de API de nuvem não configurada")

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {"model": model, "messages": messages}
        try:
            if self._external_client is not None:
                resp = await self._external_client.post(url, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=self.config.request_timeout_seconds) as client:
                    resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            text = str(data["choices"][0]["message"]["content"]).strip()
        except TierExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise TierExecutionError(tier, str(exc)) from exc

        return text, model


class CognitiveRouter:
    """Orquestra Privacy Gate, classificação, cache particionado e failover da malha."""

    def __init__(
        self,
        backend: LLMBackend,
        *,
        config: RouterConfig | None = None,
        privacy_gate: PrivacyGate | None = None,
        cache: CacheBackend | None = None,
        health: NodeHealthTracker | None = None,
        cloud_log: CloudUsageLog | None = None,
        triage_runner: TriageRunner | None = None,
    ) -> None:
        self._backend = backend
        self._config = config or RouterConfig()
        self._privacy_gate = privacy_gate or PrivacyGate()
        self._cache = cache or InMemoryCacheBackend()
        self._health = health or NodeHealthTracker(self._cache)
        self._cloud_log = cloud_log
        self._triage_runner = triage_runner

    def _build_cascade(
        self,
        primary: RouteTier,
        *,
        allow_cloud: bool,
        pc_hub_healthy: bool,
    ) -> list[RouteTier]:
        if primary == "yby-cloud-frontier":
            if allow_cloud and not self._config.offgrid_mode:
                base: list[RouteTier] = [
                    "yby-cloud-frontier",
                    "yby-code",
                    "yby-fast",
                    "yby-mobile-fallback",
                ]
            else:
                base = ["yby-code", "yby-fast", "yby-mobile-fallback"]
        elif primary == "yby-code":
            base = ["yby-code", "yby-fast", "yby-mobile-fallback"]
        elif primary == "yby-fast":
            base = ["yby-fast", "yby-code", "yby-mobile-fallback"]
        else:
            base = ["yby-mobile-fallback"]

        if not pc_hub_healthy and "yby-mobile-fallback" in base:
            # PC Hub marcado indisponível: prioriza Xiaomi 12 PocketPal antes de retentar PC Hub.
            hub_tiers = [t for t in base if t in {"yby-fast", "yby-code"}]
            non_hub = [t for t in base if t not in {"yby-fast", "yby-code"}]
            base = non_hub + hub_tiers

        # Defesa em profundidade: nunca permite nuvem se allow_cloud=False.
        if not allow_cloud:
            base = [t for t in base if t != "yby-cloud-frontier"]
        return base

    def _log_cloud_event(
        self,
        *,
        event_result: str,
        prompt: str,
        output_text: str = "",
        purpose: str = "cognitive_router",
    ) -> None:
        if self._cloud_log is None:
            return
        self._cloud_log.append(
            {
                "timestamp": utc_timestamp(),
                "provider": "cloud_frontier",
                "model": self._config.cloud_model,
                "purpose": purpose,
                "input_tokens_estimate": CloudUsageLog.estimate_tokens(prompt),
                "output_tokens_estimate": CloudUsageLog.estimate_tokens(output_text),
                "result": event_result,
            }
        )

    async def route(self, request: RouteRequest) -> RouteResponse:
        started = time.perf_counter()
        privacy = self._privacy_gate.evaluate(request)
        classification = await classify_request(
            request,
            privacy,
            triage_runner=self._triage_runner,
        )

        primary = classification.tier
        cache_key = build_cache_key(privacy.effective_sensitivity, primary, request.prompt)
        if request.use_cache:
            cached_raw = await self._cache.get(cache_key)
            if cached_raw is not None:
                cached = json.loads(cached_raw)
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                return RouteResponse(
                    text=str(cached["text"]),
                    tier=cached["tier"],
                    model=str(cached["model"]),
                    metadata=RouteMetadata(
                        selected_tier=cached["tier"],
                        attempted_tiers=[],
                        fallback_used=False,
                        cache_hit=True,
                        privacy_blocked_cloud=not privacy.allow_cloud,
                        privacy_reasons=list(privacy.blocked_reasons),
                        classifier_reasons=list(classification.reasons),
                        redaction_count=privacy.redaction_count,
                        latency_ms=round(elapsed_ms, 2),
                    ),
                )

        pc_hub_healthy = await self._health.is_healthy(PC_HUB_NODE)
        cascade = self._build_cascade(
            primary,
            allow_cloud=privacy.allow_cloud,
            pc_hub_healthy=pc_hub_healthy,
        )

        attempted: list[RouteTier] = []
        failures: list[tuple[RouteTier, str]] = []

        for tier in cascade:
            if tier == "yby-cloud-frontier" and not privacy.allow_cloud:
                # Defesa em profundidade: nunca alcança nuvem para payloads privados.
                continue

            attempted.append(tier)
            outbound_prompt = (
                privacy.sanitized_prompt if tier == "yby-cloud-frontier" else request.prompt
            )

            if tier == "yby-cloud-frontier":
                self._log_cloud_event(
                    event_result=EVENT_REQUESTED,
                    prompt=outbound_prompt,
                    purpose=f"route:{request.origin}",
                )

            try:
                text, model = await self._backend.complete(
                    tier,
                    outbound_prompt,
                    system=request.system_prompt,
                    metadata={
                        "origin": request.origin,
                        "source_node": request.source_node,
                        "sensitivity": privacy.effective_sensitivity,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                err_msg = str(exc)
                failures.append((tier, err_msg))
                if tier == "yby-cloud-frontier":
                    self._log_cloud_event(
                        event_result=EVENT_FAILED,
                        prompt=outbound_prompt,
                        purpose=f"route:{request.origin}",
                    )
                elif tier in {"yby-fast", "yby-code"}:
                    await self._health.mark_unhealthy(PC_HUB_NODE, err_msg)
                continue

            if tier == "yby-cloud-frontier":
                self._log_cloud_event(
                    event_result=EVENT_COMPLETED,
                    prompt=outbound_prompt,
                    output_text=text,
                    purpose=f"route:{request.origin}",
                )
            elif tier in {"yby-fast", "yby-code"}:
                await self._health.mark_healthy(PC_HUB_NODE)

            if request.use_cache:
                await self._cache.set(
                    cache_key,
                    json.dumps({"text": text, "tier": tier, "model": model}, ensure_ascii=False),
                    ttl_seconds=self._config.cache_ttl_seconds,
                )

            elapsed_ms = (time.perf_counter() - started) * 1000.0
            return RouteResponse(
                text=text,
                tier=tier,
                model=model,
                metadata=RouteMetadata(
                    selected_tier=tier,
                    attempted_tiers=attempted,
                    fallback_used=(tier != primary or len(failures) > 0),
                    cache_hit=False,
                    privacy_blocked_cloud=not privacy.allow_cloud,
                    privacy_reasons=list(privacy.blocked_reasons),
                    classifier_reasons=list(classification.reasons),
                    redaction_count=privacy.redaction_count,
                    latency_ms=round(elapsed_ms, 2),
                ),
            )

        raise RoutingExhaustedError(failures)
