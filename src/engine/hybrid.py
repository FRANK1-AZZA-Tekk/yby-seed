"""Um único motor: Ollama por padrão, nuvem quando o pedido pede ou o local cai."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from src.engine.budget import (
    BudgetEvaluation,
    CloudBudget,
    CODE_BLOCKED_BUDGET,
    CODE_BLOCKED_LOCAL_ONLY,
    CODE_BLOCKED_NO_TTY,
)
from src.engine.cache import ResponseCache
from src.engine.cloud_usage_log import (
    CloudUsageLog,
    EVENT_BLOCKED_BUDGET,
    EVENT_BLOCKED_LOCAL_ONLY,
    EVENT_BLOCKED_NO_TTY,
    EVENT_CANCELLED,
    EVENT_COMPLETED,
    EVENT_CONFIRMED,
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
        budget_warn_fn: Callable[[str], None] | None = None,
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
        if budget_warn_fn is not None:
            self.budget_warn_fn = budget_warn_fn
        elif confirm_fn is not None:
            self.budget_warn_fn = lambda msg: print(msg, file=sys.stderr)
        else:
            self.budget_warn_fn = lambda _msg: None
        self._cloud_session_confirmed = False

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
        try:
            text = self.ollama.complete(prompt, model=self.config.local_model, system=SYSTEM_PROMPT)
        except ProviderError as exc:
            return self._cloud_after_local_failure(prompt, decision, exc)
        return EngineReply(text, "local", self.config.local_model, decision.reasons, None)

    def _cloud_after_local_failure(
        self,
        prompt: str,
        decision: RouteDecision,
        local_error: ProviderError,
    ) -> EngineReply:
        if not self.cloud.has_credentials():
            return EngineReply(
                "",
                "none",
                "",
                decision.reasons,
                (
                    f"Ollama falhou ({local_error}). "
                    "YBY_CLOUD_API_KEY não está definida, então não há fallback de nuvem."
                ),
            )
        blocked = self._cloud_gate_reply(
            prompt,
            decision,
            purpose="ollama_fallback",
            provider_label="openrouter",
        )
        if blocked is not None:
            return EngineReply(
                "",
                "none",
                "",
                decision.reasons,
                f"Ollama falhou ({local_error}). {blocked.notice}",
            )
        try:
            result = self._cloud_call(prompt, purpose="ollama_fallback")
        except ProviderError as cloud_error:
            return EngineReply(
                "",
                "none",
                "",
                decision.reasons,
                f"Ollama falhou ({local_error}). A nuvem também falhou ({cloud_error}).",
            )
        return EngineReply(
            result.text,
            "cloud",
            result.model,
            decision.reasons,
            (
                f"Ollama falhou ({local_error}). "
                f"Respondi pela nuvem ({result.model} via {result.via})."
            ),
        )

    def _cloud_first(self, prompt: str, decision: RouteDecision) -> EngineReply:
        why = "; ".join(decision.reasons)
        if not self.cloud.has_credentials():
            return self._local_without_cloud_key(prompt, decision, why)

        blocked = self._cloud_gate_reply(prompt, decision, purpose="route_cloud")
        if blocked is not None:
            return blocked

        try:
            result = self._cloud_call(prompt, purpose="route_cloud")
        except ProviderError as cloud_error:
            return self._local_after_cloud_failure(prompt, decision, cloud_error)
        return EngineReply(result.text, "cloud", result.model, decision.reasons, None)

    def _local_without_cloud_key(
        self,
        prompt: str,
        decision: RouteDecision,
        why: str,
    ) -> EngineReply:
        prefix = (
            f"Pedido encaminhado à nuvem ({why}). YBY_CLOUD_API_KEY não está definida."
        )
        try:
            text = self.ollama.complete(prompt, model=self.config.local_model, system=SYSTEM_PROMPT)
        except ProviderError as local_error:
            return EngineReply(
                "",
                "none",
                "",
                decision.reasons,
                f"{prefix} Ollama também falhou ({local_error}).",
            )
        return EngineReply(
            text,
            "local",
            self.config.local_model,
            decision.reasons,
            f"{prefix} Respondi com o modelo local {self.config.local_model}.",
        )

    def _local_after_cloud_failure(
        self,
        prompt: str,
        decision: RouteDecision,
        cloud_error: ProviderError,
    ) -> EngineReply:
        try:
            text = self.ollama.complete(prompt, model=self.config.local_model, system=SYSTEM_PROMPT)
        except ProviderError as local_error:
            return EngineReply(
                "",
                "none",
                "",
                decision.reasons,
                f"Nuvem falhou ({cloud_error}). Ollama também falhou ({local_error}).",
            )
        return EngineReply(
            text,
            "local",
            self.config.local_model,
            decision.reasons,
            (
                f"Nuvem falhou ({cloud_error}). "
                f"Respondi com o modelo local {self.config.local_model}."
            ),
        )

    def _cloud_gate_reply(
        self,
        prompt: str,
        decision: RouteDecision,
        *,
        purpose: str,
        provider_label: str = "openrouter",
    ) -> EngineReply | None:
        evaluation = self.budget.evaluate(
            requires_confirmation=True,
            has_tty=self.has_tty_fn(),
        )
        model = self.config.cloud_model
        input_est = CloudUsageLog.estimate_tokens(prompt)

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

        cache_hit = self._cache_hit(prompt)
        if cache_hit:
            return None

        warn = _budget_warn_message(evaluation)
        if warn:
            self.budget_warn_fn(warn)

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

        needs_confirm = self.budget.require_confirm and not self._cloud_session_confirmed
        if needs_confirm:
            question = (
                "Este pedido pode usar nuvem (tokens/custo). Confirmar? [s/n]"
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

    def _cache_hit(self, prompt: str) -> bool:
        trimmed = trim_context(prompt, self.config.cloud_max_chars)
        key = self.cache.make_key(trimmed, model=self.config.cloud_model, system=SYSTEM_PROMPT)
        return self.cache.get(key) is not None

    def _cloud_call(self, prompt: str, *, purpose: str) -> CloudResult:
        trimmed = trim_context(prompt, self.config.cloud_max_chars)
        cache_model = self.config.cloud_model
        key = self.cache.make_key(trimmed, model=cache_model, system=SYSTEM_PROMPT)
        cached = self.cache.get(key)
        input_est = CloudUsageLog.estimate_tokens(trimmed)
        provider_label = "openrouter"

        if cached is not None:
            return CloudResult(cached, cache_model, "cache")

        try:
            if self.cloud_chain is not None:
                result = self.cloud_chain.complete_with_meta(trimmed, system=SYSTEM_PROMPT)
            else:
                text = self.cloud.complete(
                    trimmed, model=self.config.cloud_model, system=SYSTEM_PROMPT
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
        self.cloud_log.append(
            {
                "timestamp": utc_timestamp(),
                "provider": result.via,
                "model": result.model,
                "purpose": purpose,
                "input_tokens_estimate": input_est,
                "output_tokens_estimate": output_est,
                "result": EVENT_COMPLETED,
            }
        )
        self.cache.set(key, result.text)
        return result


def _budget_warn_message(evaluation: BudgetEvaluation) -> str | None:
    if evaluation.allowed and evaluation.reason.startswith("Aviso:"):
        return evaluation.reason
    return None


def _blocked_event(code: str) -> str:
    if code == CODE_BLOCKED_LOCAL_ONLY:
        return EVENT_BLOCKED_LOCAL_ONLY
    if code == CODE_BLOCKED_BUDGET:
        return EVENT_BLOCKED_BUDGET
    if code == CODE_BLOCKED_NO_TTY:
        return EVENT_BLOCKED_NO_TTY
    return EVENT_BLOCKED_BUDGET


def engine_from_env(
    *,
    confirm_fn: Callable[[str], bool] | None = None,
    has_tty_fn: Callable[[], bool] | None = None,
    cloud_log: CloudUsageLog | None = None,
    budget: CloudBudget | None = None,
    budget_warn_fn: Callable[[str], None] | None = None,
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
        cache=ResponseCache(ttl_seconds=config.cache_ttl_seconds),
        cloud_log=cloud_log,
        budget=budget,
        confirm_fn=confirm_fn,
        has_tty_fn=has_tty_fn,
        budget_warn_fn=budget_warn_fn,
    )
