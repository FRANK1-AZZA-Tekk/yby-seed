"""Um único motor: Ollama por padrão; nuvem só quando o roteamento pede (D12)."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.engine.budget import CloudBudget, CODE_BLOCKED_BUDGET, CODE_BLOCKED_LOCAL_ONLY, CODE_BLOCKED_NO_TTY
from src.engine.cache import ResponseCache
from src.engine.cloud_pricing import estimate_cost_usd
from src.engine.cloud_usage_log import (
    CloudUsageLog,
    EVENT_BLOCKED_AUTHZ,
    EVENT_BLOCKED_BUDGET,
    EVENT_BLOCKED_LOCAL_ONLY,
    EVENT_BLOCKED_NO_TTY,
    EVENT_CANCELLED,
    EVENT_COMPLETED,
    EVENT_CONFIRMED,
    EVENT_EXCEPTION_GRANTED,
    EVENT_FAILED,
    EVENT_REQUESTED,
    utc_timestamp,
)
from src.engine.config import EngineConfig
from src.engine.context import trim_context
from src.engine.providers import (
    CascadingCloudProvider,
    CloudClient,
    CloudProvider,
    CloudResult,
    OllamaProvider,
    ProviderError,
    TextProvider,
)
from src.engine.routing import RouteDecision, decide_route
from src.security.cloud_authz import CODE_BLOCKED_AUTHZ, check_cloud_prompt
from src.security.cloud_sanitizer import SanitizeResult, sanitize_for_cloud

SYSTEM_PROMPT = (
    "Você é o YBY SEED, um exocórtex pessoal. "
    "Responda no idioma do pedido, de forma direta e útil. "
    "Não execute comandos, não acesse arquivos e não chame ferramentas."
)

ProviderName = Literal["local", "cloud", "none"]


@dataclass(frozen=True)
class EngineReply:
    """Resposta pronta para o CLI imprimir."""

    text: str
    provider: ProviderName
    model: str
    reasons: tuple[str, ...]
    notice: str | None


class HybridEngine:
    """Decide o destino e chama um provedor, com degradação explícita."""

    def __init__(
        self,
        config: EngineConfig,
        ollama: TextProvider,
        cloud: CloudClient,
        *,
        cache: ResponseCache | None = None,
        cloud_chain: CascadingCloudProvider | None = None,
        cloud_log: CloudUsageLog | None = None,
        budget: CloudBudget | None = None,
        confirm_fn: Callable[[str], bool] | None = None,
        has_tty_fn: Callable[[], bool] | None = None,
    ) -> None:
        self.config = config
        self.ollama = ollama
        self.cloud = cloud
        self.cloud_chain = cloud_chain
        self.cache = cache or ResponseCache(ttl_seconds=config.cache_ttl_seconds)
        self.cloud_log = cloud_log or CloudUsageLog.from_env()
        self.budget = budget or CloudBudget.from_env()
        if confirm_fn is None:
            self.confirm_fn = lambda _msg: True
            self.has_tty_fn = has_tty_fn or (lambda: True)
        else:
            self.confirm_fn = confirm_fn
            self.has_tty_fn = has_tty_fn or (
                lambda: sys.stdin.isatty() and sys.stdout.isatty()
            )
        self._cloud_session_confirmed = False
        self._budget_warn: str | None = None
        self._sanitize_notice: str | None = None

    def reply(self, prompt: str, *, explicit_heavy: bool = False) -> EngineReply:
        decision = decide_route(
            prompt,
            explicit_heavy=explicit_heavy,
            heavy_min_chars=self.config.heavy_min_chars,
            heavy_min_lines=self.config.heavy_min_lines,
            heavy_min_questions=self.config.heavy_min_questions,
            heavy_phrases=self.config.heavy_phrases,
        )
        if decision.target == "cloud":
            return self._cloud_first(prompt, decision)
        return self._local_first(prompt, decision)

    def _local_first(self, prompt: str, decision: RouteDecision) -> EngineReply:
        cached = self._lookup(prompt, model=self.config.local_model)
        if cached is not None:
            return EngineReply(cached, "local", self.config.local_model, decision.reasons, None)
        try:
            text = self.ollama.complete(prompt, model=self.config.local_model, system=SYSTEM_PROMPT)
        except ProviderError as exc:
            return self._after_local_failure(decision, exc)
        self._store(prompt, text, model=self.config.local_model)
        return EngineReply(text, "local", self.config.local_model, decision.reasons, None)

    def _after_local_failure(
        self,
        decision: RouteDecision,
        local_error: ProviderError,
    ) -> EngineReply:
        """Falha Ollama no caminho local não dispara nuvem (D12 / fase P / #42)."""

        return EngineReply(
            "",
            "none",
            "",
            decision.reasons,
            (
                f"Ollama falhou ({local_error}). "
                "Nuvem não é acionada automaticamente após falha local (D12 / fase P). "
                "Use --heavy ou confirme nuvem quando o roteamento pedir capacidade extra."
            ),
        )

    def _cloud_first(self, prompt: str, decision: RouteDecision) -> EngineReply:
        why = "; ".join(decision.reasons)
        cached = self._lookup_cloud(prompt)
        if cached is not None:
            return EngineReply(
                cached,
                "cloud",
                self.config.cloud_model,
                decision.reasons,
                self._compose_cloud_notice(),
            )
        if not self.cloud.has_credentials():
            return self._local_without_cloud_key(prompt, decision, why)

        blocked = self._cloud_gate_reply(prompt, decision, purpose="route_cloud")
        if blocked is not None:
            # D12: teto/TTY/local_only não deve matar o ask se o Ollama responde.
            return self._local_after_cloud_block(
                prompt,
                decision,
                blocked.notice or "nuvem bloqueada",
            )

        try:
            result = self._cloud_call(prompt, purpose="route_cloud")
        except ProviderError as cloud_error:
            return self._local_after_cloud_failure(prompt, decision, cloud_error)
        return EngineReply(
            result.text,
            "cloud",
            result.model,
            decision.reasons,
            self._compose_cloud_notice(),
        )

    def _local_without_cloud_key(
        self,
        prompt: str,
        decision: RouteDecision,
        why: str,
    ) -> EngineReply:
        prefix = (
            f"Pedido encaminhado à nuvem ({why}). YBY_CLOUD_API_KEY não está definida."
        )
        return self._reply_from_local(
            prompt,
            decision,
            prefix=prefix,
            failure_prefix=prefix,
        )

    def _local_after_cloud_failure(
        self,
        prompt: str,
        decision: RouteDecision,
        cloud_error: ProviderError,
    ) -> EngineReply:
        prefix = f"Nuvem falhou ({cloud_error})."
        return self._reply_from_local(
            prompt,
            decision,
            prefix=prefix,
            failure_prefix=prefix,
        )

    def _local_after_cloud_block(
        self,
        prompt: str,
        decision: RouteDecision,
        reason: str,
    ) -> EngineReply:
        clean = reason.strip().rstrip(".")
        prefix = f"Nuvem indisponível ({clean})."
        return self._reply_from_local(
            prompt,
            decision,
            prefix=prefix,
            failure_prefix=prefix,
        )

    def _reply_from_local(
        self,
        prompt: str,
        decision: RouteDecision,
        *,
        prefix: str,
        failure_prefix: str,
    ) -> EngineReply:
        cached = self._lookup(prompt, model=self.config.local_model)
        if cached is not None:
            return EngineReply(
                cached,
                "local",
                self.config.local_model,
                decision.reasons,
                f"{prefix} Respondi com o cache local ({self.config.local_model}).",
            )
        try:
            text = self.ollama.complete(
                prompt, model=self.config.local_model, system=SYSTEM_PROMPT
            )
        except ProviderError as local_error:
            return EngineReply(
                "",
                "none",
                "",
                decision.reasons,
                f"{failure_prefix} Ollama também falhou ({local_error}).",
            )
        self._store(prompt, text, model=self.config.local_model)
        return EngineReply(
            text,
            "local",
            self.config.local_model,
            decision.reasons,
            f"{prefix} Respondi com o modelo local {self.config.local_model}.",
        )

    def _cloud_gate_reply(
        self,
        prompt: str,
        decision: RouteDecision,
        *,
        purpose: str,
        provider_label: str = "openrouter",
    ) -> EngineReply | None:
        model = self.config.cloud_model
        input_est = CloudUsageLog.estimate_tokens(prompt)
        self._budget_warn = None

        # §6.1 passo 3: authz vault antes de budget/confirm/HTTP.
        authz = check_cloud_prompt(prompt)
        if not authz.allowed:
            self.cloud_log.append(
                {
                    "timestamp": utc_timestamp(),
                    "provider": provider_label,
                    "model": model,
                    "purpose": purpose,
                    "input_tokens_estimate": input_est,
                    "output_tokens_estimate": 0,
                    "result": EVENT_BLOCKED_AUTHZ,
                }
            )
            return EngineReply("", "none", "", decision.reasons, authz.reason)

        evaluation = self.budget.evaluate(
            requires_confirmation=True,
            has_tty=self.has_tty_fn(),
        )

        if not evaluation.allowed:
            event = {
                "timestamp": utc_timestamp(),
                "provider": provider_label,
                "model": model,
                "purpose": purpose,
                "input_tokens_estimate": input_est,
                "output_tokens_estimate": 0,
                "result": _blocked_event(evaluation.code),
            }
            self.cloud_log.append(event)
            return EngineReply("", "none", "", decision.reasons, evaluation.reason)

        if evaluation.exception_granted:
            self.cloud_log.append(
                {
                    "timestamp": utc_timestamp(),
                    "provider": provider_label,
                    "model": model,
                    "purpose": purpose,
                    "input_tokens_estimate": input_est,
                    "output_tokens_estimate": 0,
                    "result": EVENT_EXCEPTION_GRANTED,
                    "meta": {"exception": True},
                }
            )
            self._budget_warn = evaluation.reason
        elif evaluation.reason.startswith("Aviso:"):
            self._budget_warn = evaluation.reason

        self.cloud_log.append(
            {
                "timestamp": utc_timestamp(),
                "provider": provider_label,
                "model": model,
                "purpose": purpose,
                "input_tokens_estimate": input_est,
                "output_tokens_estimate": 0,
                "result": EVENT_REQUESTED,
            }
        )

        est_cost = estimate_cost_usd(
            provider=provider_label,
            model=model,
            input_tokens=input_est,
            output_tokens=0,
        )
        needs_confirm = self.budget.should_confirm(
            input_tokens=input_est,
            estimated_cost_usd=est_cost,
            purpose=purpose,
            session_confirmed=self._cloud_session_confirmed,
            evaluation=evaluation,
        )
        if needs_confirm:
            if not self.has_tty_fn() and not self.budget.allow_no_tty:
                self.cloud_log.append(
                    {
                        "timestamp": utc_timestamp(),
                        "provider": provider_label,
                        "model": model,
                        "purpose": purpose,
                        "input_tokens_estimate": input_est,
                        "output_tokens_estimate": 0,
                        "result": EVENT_BLOCKED_NO_TTY,
                    }
                )
                return EngineReply(
                    "",
                    "none",
                    "",
                    decision.reasons,
                    "Confirmação de nuvem exige TTY (stdin/stdout interativo).",
                )
            question = (
                f"Nuvem {provider_label}/{model} ({purpose}): "
                f"~{input_est} tokens in, ~${est_cost:.4f}. Confirmar? [s/n]"
            )
            if not self.confirm_fn(question):
                self.cloud_log.append(
                    {
                        "timestamp": utc_timestamp(),
                        "provider": provider_label,
                        "model": model,
                        "purpose": purpose,
                        "input_tokens_estimate": input_est,
                        "output_tokens_estimate": 0,
                        "result": EVENT_CANCELLED,
                    }
                )
                return EngineReply(
                    "",
                    "none",
                    "",
                    decision.reasons,
                    "Uso de nuvem cancelado pelo usuário.",
                )
            self._cloud_session_confirmed = True
            self.cloud_log.append(
                {
                    "timestamp": utc_timestamp(),
                    "provider": provider_label,
                    "model": model,
                    "purpose": purpose,
                    "input_tokens_estimate": input_est,
                    "output_tokens_estimate": 0,
                    "result": EVENT_CONFIRMED,
                }
            )
        return None

    def _lookup(self, prompt: str, *, model: str) -> str | None:
        key = self.cache.make_key(prompt, model=model, system=SYSTEM_PROMPT)
        return self.cache.get(key)

    def _lookup_cloud(self, prompt: str) -> str | None:
        outbound, _stats = self._prepare_cloud_prompt(prompt)
        return self._lookup(outbound, model=self.config.cloud_model)

    def _store(self, prompt: str, text: str, *, model: str) -> None:
        key = self.cache.make_key(prompt, model=model, system=SYSTEM_PROMPT)
        self.cache.set(key, text)

    def _prepare_cloud_prompt(self, prompt: str) -> tuple[str, SanitizeResult]:
        """Trim + sanitize antes de cache/HTTP (nunca enviar segredos/PII crus)."""

        trimmed = trim_context(prompt, self.config.cloud_max_chars)
        stats = sanitize_for_cloud(trimmed)
        if stats.enabled and stats.redactions > 0:
            self._sanitize_notice = (
                f"Nuvem: {stats.redactions} dado(s) sensível(is) redactado(s) no envio."
            )
        else:
            self._sanitize_notice = None
        return stats.text, stats

    def _compose_cloud_notice(self) -> str | None:
        parts = [p for p in (self._budget_warn, self._sanitize_notice) if p]
        if not parts:
            return None
        return " ".join(parts)

    def _cloud_call(self, prompt: str, *, purpose: str) -> CloudResult:
        # Authz defensivo antes de cache/HTTP (T10 / §6.1).
        authz = check_cloud_prompt(prompt)
        provider_label = "openrouter"
        cache_model = self.config.cloud_model
        if not authz.allowed:
            self.cloud_log.append(
                {
                    "timestamp": utc_timestamp(),
                    "provider": provider_label,
                    "model": cache_model,
                    "purpose": purpose,
                    "input_tokens_estimate": CloudUsageLog.estimate_tokens(prompt),
                    "output_tokens_estimate": 0,
                    "result": EVENT_BLOCKED_AUTHZ,
                }
            )
            raise ProviderError(authz.reason or "blocked_authz")

        outbound, _stats = self._prepare_cloud_prompt(prompt)
        key = self.cache.make_key(outbound, model=cache_model, system=SYSTEM_PROMPT)
        cached = self.cache.get(key)
        input_est = CloudUsageLog.estimate_tokens(outbound)

        if cached is not None:
            return CloudResult(cached, cache_model, "cache")

        try:
            if self.cloud_chain is not None:
                result = self.cloud_chain.complete_with_meta(outbound, system=SYSTEM_PROMPT)
            else:
                text = self.cloud.complete(
                    outbound, model=self.config.cloud_model, system=SYSTEM_PROMPT
                )
                result = CloudResult(text, self.config.cloud_model, "cloud")
        except ProviderError as exc:
            self.cloud_log.append(
                {
                    "timestamp": utc_timestamp(),
                    "provider": provider_label,
                    "model": cache_model,
                    "purpose": purpose,
                    "input_tokens_estimate": input_est,
                    "output_tokens_estimate": 0,
                    "result": EVENT_FAILED,
                }
            )
            raise exc

        output_est = CloudUsageLog.estimate_tokens(result.text)
        cost = estimate_cost_usd(
            provider=result.via,
            model=result.model,
            input_tokens=input_est,
            output_tokens=output_est,
        )
        self.cloud_log.append(
            {
                "timestamp": utc_timestamp(),
                "provider": result.via,
                "model": result.model,
                "purpose": purpose,
                "input_tokens_estimate": input_est,
                "output_tokens_estimate": output_est,
                "estimated_cost_usd": cost,
                "result": EVENT_COMPLETED,
            }
        )
        self.cache.set(key, result.text)
        return result


def _blocked_event(code: str) -> str:
    if code == CODE_BLOCKED_LOCAL_ONLY:
        return EVENT_BLOCKED_LOCAL_ONLY
    if code == CODE_BLOCKED_BUDGET:
        return EVENT_BLOCKED_BUDGET
    if code == CODE_BLOCKED_NO_TTY:
        return EVENT_BLOCKED_NO_TTY
    if code == CODE_BLOCKED_AUTHZ:
        return EVENT_BLOCKED_AUTHZ
    return EVENT_BLOCKED_BUDGET


def _response_cache(config: EngineConfig) -> ResponseCache:
    """Cache em memória, ou em disco para o CLI que sai a cada pedido."""

    ttl = config.cache_ttl_seconds
    if ttl <= 0:
        return ResponseCache(ttl_seconds=ttl)
    raw = os.environ.get("YBY_CACHE_PATH", "").strip()
    if raw.casefold() in {"memory", "off", "0", "-"}:
        return ResponseCache(ttl_seconds=ttl)
    path = (
        Path(raw).expanduser()
        if raw
        else Path.home() / ".local" / "state" / "yby-seed" / "response-cache.json"
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return ResponseCache(ttl_seconds=ttl)
    return ResponseCache(ttl_seconds=ttl, path=path)


def engine_from_env(
    *,
    confirm_fn: Callable[[str], bool] | None = None,
    has_tty_fn: Callable[[], bool] | None = None,
    cloud_log: CloudUsageLog | None = None,
    budget: CloudBudget | None = None,
) -> HybridEngine:
    """Monta o motor com os clientes HTTP reais e a configuração do ambiente."""

    config = EngineConfig.from_env()
    primary = CloudProvider(
        config.cloud_base_url,
        api_key=config.cloud_api_key,
        timeout=config.cloud_timeout,
    )
    fallback = CloudProvider(
        config.cloud_fallback_base_url,
        api_key=config.cloud_fallback_api_key,
        timeout=config.cloud_timeout,
    )
    chain = CascadingCloudProvider(
        primary,
        primary_model=config.cloud_model,
        primary_label="openrouter",
        fallback=fallback,
        fallback_model=config.cloud_fallback_model,
        fallback_label="grok",
    )
    return HybridEngine(
        config,
        ollama=OllamaProvider(config.ollama_base_url, timeout=config.ollama_timeout),
        cloud=chain,
        cloud_chain=chain,
        cache=_response_cache(config),
        cloud_log=cloud_log,
        budget=budget,
        confirm_fn=confirm_fn,
        has_tty_fn=has_tty_fn,
    )
