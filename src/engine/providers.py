"""Clientes HTTP do Ollama e de endpoints compatíveis com a API da OpenAI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import requests


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
                json={
                    "model": model,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                },
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
        return text


@dataclass(frozen=True)
class CloudResult:
    """Resposta de nuvem com o modelo que de fato respondeu."""

    text: str
    model: str
    via: str


class CascadingCloudProvider:
    """OpenRouter (ou outro primário) e, se falhar, Grok (fallback)."""

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
        if self.primary.has_credentials():
            return True
        return bool(self.fallback and self.fallback.has_credentials())

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        """Protocolo CloudClient: tenta primário e depois fallback."""

        return self.complete_with_meta(prompt, system=system).text

    def complete_with_meta(self, prompt: str, *, system: str) -> CloudResult:
        """Tenta o destino primário; em falha, o fallback (Grok)."""

        primary_error: ProviderError | None = None
        if self.primary.has_credentials():
            try:
                text = self.primary.complete(
                    prompt, model=self.primary_model, system=system
                )
                return CloudResult(text, self.primary_model, self.primary_label)
            except ProviderError as exc:
                primary_error = exc
        elif self.fallback is None or not self.fallback.has_credentials():
            raise ProviderError("YBY_CLOUD_API_KEY não está definida.")

        if self.fallback is None or not self.fallback.has_credentials():
            assert primary_error is not None
            raise primary_error

        try:
            text = self.fallback.complete(
                prompt, model=self.fallback_model, system=system
            )
        except ProviderError as fallback_error:
            if primary_error is not None:
                raise ProviderError(
                    f"{self.primary_label} falhou ({primary_error}); "
                    f"{self.fallback_label} falhou ({fallback_error})"
                ) from fallback_error
            raise fallback_error

        return CloudResult(text, self.fallback_model, self.fallback_label)


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
