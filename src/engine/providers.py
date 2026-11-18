"""Clientes HTTP do Ollama e de endpoints compatíveis com a API da OpenAI."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Protocol

import requests

DEFAULT_OLLAMA_KEEP_ALIVE = "30m"
DEFAULT_OLLAMA_NUM_CTX = 4096
DEFAULT_OLLAMA_NUM_PREDICT = 1024
_RETRY_STATUS = frozenset({429, 502, 503, 504})


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


def _ollama_runtime_tuning() -> tuple[str, int, int, bool]:
    """Lê tunables locais do ambiente (sem nuvem)."""

    keep_alive = os.environ.get("OLLAMA_KEEP_ALIVE", DEFAULT_OLLAMA_KEEP_ALIVE).strip()
    if not keep_alive:
        keep_alive = DEFAULT_OLLAMA_KEEP_ALIVE
    num_ctx = _env_int("YBY_OLLAMA_NUM_CTX", DEFAULT_OLLAMA_NUM_CTX, minimum=1)
    num_predict = _env_int("YBY_OLLAMA_NUM_PREDICT", DEFAULT_OLLAMA_NUM_PREDICT, minimum=-1)
    if num_predict == 0:
        num_predict = DEFAULT_OLLAMA_NUM_PREDICT
    think = os.environ.get("YBY_OLLAMA_THINK", "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
        "sim",
    }
    return keep_alive, num_ctx, num_predict, think


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value < minimum:
        return default
    return value


def build_ollama_generate_payload(
    prompt: str,
    *,
    model: str,
    system: str,
) -> dict[str, Any]:
    """Corpo JSON de `POST /api/generate`.

    `think` fica no topo (não em `options`): em modelos com raciocínio o
    Ollama ignora `options.think` e gasta `num_predict` inteiro no campo
    `thinking`, devolvendo `response` vazio. `num_ctx` 4096 cabe na GTX 1650
    4 GB sem spill para CPU. `num_predict` limita a geração para caber no
    timeout antes de cair na nuvem.
    """

    keep_alive, num_ctx, num_predict, think = _ollama_runtime_tuning()
    return {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "think": think,
        "keep_alive": keep_alive,
        "options": {"num_ctx": num_ctx, "num_predict": num_predict},
    }


def _request_timeout(total: float) -> tuple[float, float]:
    """Conexão curta, leitura longa. Um Ollama caído não espera o timeout inteiro."""

    return (min(5.0, total), total)


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
                timeout=_request_timeout(self.timeout),
            )
        except requests.RequestException as exc:
            raise ProviderUnreachable(f"Ollama indisponível em {self.base_url} ({exc})") from exc

        if response.status_code >= 400:
            raise ProviderError(f"Ollama respondeu HTTP {response.status_code} em {self.base_url}.")

        payload = _json_object(response, "Ollama")
        return _ollama_text(payload, model)


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
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        timeout = _request_timeout(self.timeout)
        response: Any = None
        last_error: requests.RequestException | None = None
        for attempt in (1, 2):
            try:
                response = self._session.post(url, headers=headers, json=body, timeout=timeout)
            except requests.RequestException as exc:
                last_error = exc
                if attempt == 1:
                    time.sleep(0.25)
                    continue
                raise ProviderUnreachable(
                    f"Nuvem indisponível em {self.base_url} ({exc})"
                ) from exc
            last_error = None
            if response.status_code in _RETRY_STATUS and attempt == 1:
                time.sleep(_retry_wait(response))
                continue
            break

        if last_error is not None:
            raise ProviderUnreachable(
                f"Nuvem indisponível em {self.base_url} ({last_error})"
            ) from last_error
        if response is None or response.status_code >= 400:
            status = getattr(response, "status_code", "?")
            raise ProviderError(f"Nuvem respondeu HTTP {status} em {self.base_url}.")

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
            text = self.primary.complete(
                prompt, model=self.primary_model, system=system
            )
        except ProviderError as exc:
            raise ProviderError(
                f"{self.primary_label} falhou ({exc}). "
                "Nuvem alternativa não é chamada automaticamente (D12)."
            ) from exc
        return CloudResult(text, self.primary_model, self.primary_label)


def _retry_wait(response: Any) -> float:
    headers = getattr(response, "headers", None)
    raw = ""
    if headers is not None:
        getter = getattr(headers, "get", None)
        if callable(getter):
            raw = str(getter("Retry-After", "")).strip()
    try:
        delay = float(raw) if raw else 0.25
    except ValueError:
        delay = 0.25
    if delay < 0:
        delay = 0.25
    # OpenRouter pode mandar Retry-After alto; o CLI não espera um minuto.
    return min(delay, 5.0)


def _ollama_text(payload: dict[str, Any], model: str) -> str:
    error = payload.get("error")
    if isinstance(error, str) and error.strip():
        raise ProviderError(f"Ollama ({model}) devolveu erro: {error.strip()}")

    response = payload.get("response")
    thinking = payload.get("thinking")
    text = response.strip() if isinstance(response, str) else ""
    if not text and isinstance(thinking, str):
        text = thinking.strip()
    if text:
        return text

    reason = payload.get("done_reason")
    suffix = f" done_reason={reason}." if isinstance(reason, str) and reason else ""
    raise ProviderError(f"Ollama ({model}) devolveu uma resposta vazia.{suffix}")


def _json_object(response: requests.Response, who: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderError(f"{who} devolveu um corpo que não é JSON.") from exc
    if not isinstance(payload, dict):
        raise ProviderError(f"{who} devolveu um JSON que não é um objeto.")
    return payload


def _message_content(payload: dict[str, Any]) -> str:
    if not payload.get("choices"):
        error = payload.get("error")
        if error is not None:
            detail = error.get("message") if isinstance(error, dict) else error
            raise ProviderError(f"A nuvem devolveu erro: {detail}")

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderError("A nuvem não devolveu choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise ProviderError("A nuvem devolveu uma choice inválida.")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ProviderError("A nuvem não devolveu message.")

    text = _coerce_text(message.get("content")).strip()
    if text:
        return text
    for key in ("reasoning", "reasoning_content"):
        alt = message.get(key)
        if isinstance(alt, str) and alt.strip():
            return alt.strip()
    details = message.get("reasoning_details")
    if isinstance(details, list):
        parts: list[str] = []
        for item in details:
            if not isinstance(item, dict):
                continue
            bit = item.get("text") or item.get("summary")
            if isinstance(bit, str) and bit.strip():
                parts.append(bit.strip())
        if parts:
            return "\n".join(parts)
    raise ProviderError("A nuvem não devolveu message.content.")


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            bit = item.get("text") or item.get("content")
            if isinstance(bit, str):
                parts.append(bit)
    return "".join(parts)
