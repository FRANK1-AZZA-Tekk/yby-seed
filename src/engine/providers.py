"""Clientes HTTP do Ollama e de endpoints compatíveis com a API da OpenAI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

import requests

DEFAULT_OLLAMA_KEEP_ALIVE = "30m"
DEFAULT_OLLAMA_NUM_CTX = 4096


class ProviderError(Exception):
    """O provedor respondeu de um jeito que não dá para usar."""


class ProviderUnreachable(ProviderError):
    """Não houve conexão com o provedor."""


class TextProvider(Protocol):
    """Gera texto para um modelo já escolhido."""

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        """Devolve o texto do modelo ou levanta ProviderError."""


class CloudClient(Protocol):
    """Nuvem com chave opcional. Sem chave, o motor não chama `complete`."""

    def has_credentials(self) -> bool:
        """Diz se há uma chave não vazia."""

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        """Devolve o texto do modelo ou levanta ProviderError."""


class HttpSession(Protocol):
    """Fatia de `requests.Session` usada pelos provedores."""

    def post(self, url: str, **kwargs: Any) -> Any:
        """Envia um POST e devolve uma resposta com status e JSON."""


def _ollama_runtime_tuning() -> tuple[str, int]:
    """Lê tunables locais do ambiente (sem nuvem)."""

    keep_alive = os.environ.get("OLLAMA_KEEP_ALIVE", DEFAULT_OLLAMA_KEEP_ALIVE).strip()
    if not keep_alive:
        keep_alive = DEFAULT_OLLAMA_KEEP_ALIVE
    raw_ctx = os.environ.get("YBY_OLLAMA_NUM_CTX", str(DEFAULT_OLLAMA_NUM_CTX)).strip()
    try:
        num_ctx = int(raw_ctx) if raw_ctx else DEFAULT_OLLAMA_NUM_CTX
    except ValueError:
        num_ctx = DEFAULT_OLLAMA_NUM_CTX
    return keep_alive, num_ctx


def build_ollama_generate_payload(
    prompt: str,
    *,
    model: str,
    system: str,
) -> dict[str, Any]:
    """Corpo JSON de `POST /api/generate` com keep_alive e num_ctx."""

    keep_alive, num_ctx = _ollama_runtime_tuning()
    return {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {"num_ctx": num_ctx},
    }


class OllamaProvider:
    """Cliente mínimo de `POST /api/generate`."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float,
        session: HttpSession | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        url = f"{self.base_url}/api/generate"
        try:
            response = self._session.post(
                url,
                json=build_ollama_generate_payload(prompt, model=model, system=system),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ProviderUnreachable(f"Ollama indisponível em {self.base_url} ({exc})") from exc

        if response.status_code >= 400:
            raise ProviderError(f"Ollama respondeu HTTP {response.status_code} em {self.base_url}.")

        payload = _json_object(response, "Ollama")
        text = payload.get("response")
        if not isinstance(text, str) or not text.strip():
            raise ProviderError(f"Ollama ({model}) devolveu uma resposta vazia.")
        return text


class CloudProvider:
    """Cliente de `POST {base}/chat/completions` com bearer token."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str,
        timeout: float,
        session: HttpSession | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.timeout = timeout
        self._session = session or requests.Session()

    def has_credentials(self) -> bool:
        return bool(self.api_key)

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        return self.complete_with_meta(prompt, model=model, system=system).text

    def complete_with_meta(self, prompt: str, *, model: str, system: str) -> CloudResult:
        if not self.has_credentials():
            raise ProviderError("YBY_CLOUD_API_KEY não está definida.")

        url = f"{self.base_url}/chat/completions"
        try:
            response = self._session.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ProviderUnreachable(f"Nuvem indisponível em {self.base_url} ({exc})") from exc

        if response.status_code >= 400:
            raise ProviderError(f"Nuvem respondeu HTTP {response.status_code} em {self.base_url}.")

        payload = _json_object(response, "A nuvem")
        text = _message_content(payload)
        if not text.strip():
            raise ProviderError(f"Nuvem ({model}) devolveu uma resposta vazia.")
        input_tokens, output_tokens = _usage_tokens(payload)
        return CloudResult(
            text,
            model,
            "cloud",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


@dataclass(frozen=True)
class CloudResult:
    """Resposta de nuvem com o modelo que de fato respondeu."""

    text: str
    model: str
    via: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class CascadingCloudProvider:
    """Nuvem primária (ex.: OpenRouter). Sem failover automático para Grok (D12).

    Fallback alternativo fica no construtor até a issue #42 (confirmação explícita);
    não é chamado em `complete_with_meta`.
    """

    def __init__(
        self,
        primary: CloudProvider,
        *,
        primary_model: str,
        primary_label: str = "openrouter",
        fallback: CloudProvider | None = None,
        fallback_model: str = "",
        fallback_label: str = "grok",
    ) -> None:
        self.primary = primary
        self.primary_model = primary_model
        self.primary_label = primary_label
        self.fallback = fallback
        self.fallback_model = fallback_model
        self.fallback_label = fallback_label

    def has_credentials(self) -> bool:
        return self.primary.has_credentials()

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        """Protocolo CloudClient: apenas o provedor primário."""

        return self.complete_with_meta(prompt, system=system).text

    def complete_with_meta(self, prompt: str, *, system: str) -> CloudResult:
        """Chama só o destino primário; falha não dispara Grok (confirmação futura #42)."""

        if not self.primary.has_credentials():
            raise ProviderError(
                "YBY_CLOUD_API_KEY não está definida. "
                "Fallback de nuvem exige autorização explícita (issue #42)."
            )
        try:
            result = _primary_complete_with_meta(
                self.primary,
                prompt,
                model=self.primary_model,
                system=system,
            )
        except ProviderError as exc:
            raise ProviderError(
                f"{self.primary_label} falhou ({exc}). "
                "Nuvem alternativa não é chamada automaticamente (D12)."
            ) from exc
        return CloudResult(
            result.text,
            self.primary_model,
            self.primary_label,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )


def _primary_complete_with_meta(
    primary: CloudClient,
    prompt: str,
    *,
    model: str,
    system: str,
) -> CloudResult:
    """Aceita CloudProvider ou fake só com `complete` (testes)."""

    meta = getattr(primary, "complete_with_meta", None)
    if callable(meta):
        result = meta(prompt, model=model, system=system)
        if isinstance(result, CloudResult):
            return result
        if isinstance(result, str):
            return CloudResult(result, model, "cloud")
        raise ProviderError("complete_with_meta devolveu um tipo inválido.")
    text = primary.complete(prompt, model=model, system=system)
    return CloudResult(text, model, "cloud")


def _json_object(response: requests.Response, who: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderError(f"{who} devolveu um corpo que não é JSON.") from exc
    if not isinstance(payload, dict):
        raise ProviderError(f"{who} devolveu um JSON que não é um objeto.")
    return payload


def _message_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderError("A nuvem não devolveu choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise ProviderError("A nuvem devolveu uma choice inválida.")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ProviderError("A nuvem não devolveu message.")
    content = message.get("content")
    if not isinstance(content, str):
        raise ProviderError("A nuvem não devolveu message.content.")
    return content


def _usage_tokens(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None, None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    input_tokens = prompt if isinstance(prompt, int) else None
    output_tokens = completion if isinstance(completion, int) else None
    return input_tokens, output_tokens
