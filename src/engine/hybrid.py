"""Um único motor: Ollama por padrão, nuvem quando o pedido pede ou o local cai."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.engine.cache import ResponseCache
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
    ) -> None:
        self.config = config
        self.ollama = ollama
        self.cloud = cloud
        self.cloud_chain = cloud_chain
        self.cache = cache or ResponseCache(ttl_seconds=config.cache_ttl_seconds)

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
        try:
            result = self._cloud_call(prompt)
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

        try:
            result = self._cloud_call(prompt)
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

    def _cloud_call(self, prompt: str) -> CloudResult:
        """Trunca contexto, consulta cache e chama a cadeia OpenRouter→Grok."""

        trimmed = trim_context(prompt, self.config.cloud_max_chars)
        cache_model = self.config.cloud_model
        key = self.cache.make_key(trimmed, model=cache_model, system=SYSTEM_PROMPT)
        cached = self.cache.get(key)
        if cached is not None:
            return CloudResult(cached, cache_model, "cache")

        if self.cloud_chain is not None:
            result = self.cloud_chain.complete_with_meta(trimmed, system=SYSTEM_PROMPT)
        else:
            text = self.cloud.complete(
                trimmed, model=self.config.cloud_model, system=SYSTEM_PROMPT
            )
            result = CloudResult(text, self.config.cloud_model, "cloud")

        self.cache.set(key, result.text)
        return result


def engine_from_env() -> HybridEngine:
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
    )
