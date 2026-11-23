"""Cliente HTTP para Mem0/Supabase com retry (local-first, D3)."""

from __future__ import annotations

import time
from typing import Any, Protocol

import requests

_RETRY_STATUS = frozenset({408, 429, 502, 503, 504})
_MAX_ATTEMPTS = 3


class RemoteStoreError(RuntimeError):
    """Falha ao persistir episódio remoto."""


class EpisodeRemoteClient(Protocol):
    """Contrato mínimo (Mem0 ``add`` ou REST Supabase)."""

    def add(
        self,
        messages: list[dict[str, str]],
        *,
        user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ...


class HttpSession(Protocol):
    def post(self, url: str, **kwargs: Any) -> Any:
        ...


def _backoff_seconds(attempt: int) -> float:
    return min(0.25 * (2 ** (attempt - 1)), 5.0)


def post_with_retry(
    session: HttpSession,
    url: str,
    *,
    json_body: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: tuple[float, float] = (5.0, 30.0),
) -> Any:
    last_error: requests.RequestException | None = None
    response: Any = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            kwargs: dict[str, Any] = {"json": json_body, "timeout": timeout}
            if headers:
                kwargs["headers"] = headers
            response = session.post(url, **kwargs)
        except requests.RequestException as exc:
            last_error = exc
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_backoff_seconds(attempt))
                continue
            raise RemoteStoreError("rede indisponível ao gravar episódio") from exc
        if response.status_code in _RETRY_STATUS and attempt < _MAX_ATTEMPTS:
            time.sleep(_backoff_seconds(attempt))
            continue
        if response.status_code >= 400:
            raise RemoteStoreError(f"HTTP {response.status_code} ao gravar episódio")
        return response
    if last_error is not None:
        raise RemoteStoreError("rede indisponível ao gravar episódio") from last_error
    return response


class Mem0HttpClient:
    """Envia episódios para endpoint compatível (POST JSON). Não loga tokens."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str = "",
        session: HttpSession | None = None,
        timeout: tuple[float, float] = (5.0, 30.0),
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self._session = session or requests.Session()
        self._timeout = timeout

    def close(self) -> None:
        closer = getattr(self._session, "close", None)
        if callable(closer):
            closer()

    def add(
        self,
        messages: list[dict[str, str]],
        *,
        user_id: str = "yby",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        url = f"{self.base_url}/v1/memories"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body: dict[str, Any] = {"messages": messages, "user_id": user_id}
        if metadata:
            body["metadata"] = metadata
        post_with_retry(self._session, url, json_body=body, headers=headers, timeout=self._timeout)