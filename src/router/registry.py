"""Registro de modelos locais do roteador offline (sem carregar pesos)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Mapping

from src.router.errors import ConfigurationError, ModelNotFoundError, SafetyViolationError
from src.router.policy import ALLOWED_TOOLS

Provider = Literal["ollama", "local"]
ModelRole = Literal["general", "coder", "fallback", "embeddings"]

UNCENSORED_MARKERS: tuple[str, ...] = (
    "uncensored",
    "unfiltered",
    "dolphin-uncensored",
    "abliterated",
)

DEFAULT_PROVIDER: Provider = "ollama"
DEFAULT_CONTEXT = 8192
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class ModelEntry:
    """Metadados de um modelo local registrado."""

    role: ModelRole
    provider: Provider
    model: str
    context: int
    max_tokens: int
    timeout: float
    enabled: bool = True
    allow_cloud: bool = False
    allowed_tools: frozenset[str] = frozenset()
    is_agent_primary: bool = False

    @property
    def key(self) -> str:
        return self.role


def default_entries() -> tuple[ModelEntry, ...]:
    """Catálogo padrão local-first (somente nomes; sem I/O)."""

    return (
        ModelEntry(
            role="general",
            provider=DEFAULT_PROVIDER,
            model="qwen3-8b-instruct",
            context=DEFAULT_CONTEXT,
            max_tokens=DEFAULT_MAX_TOKENS,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            enabled=True,
            allow_cloud=False,
            allowed_tools=frozenset(),
            is_agent_primary=True,
        ),
        ModelEntry(
            role="coder",
            provider=DEFAULT_PROVIDER,
            model="qwen2.5-coder-7b-instruct",
            context=DEFAULT_CONTEXT,
            max_tokens=DEFAULT_MAX_TOKENS,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            enabled=True,
            allow_cloud=False,
            allowed_tools=frozenset(),
            is_agent_primary=True,
        ),
        ModelEntry(
            role="fallback",
            provider=DEFAULT_PROVIDER,
            model="qwen3-4b-instruct",
            context=4096,
            max_tokens=1024,
            timeout=45.0,
            enabled=True,
            allow_cloud=False,
            allowed_tools=frozenset(),
            is_agent_primary=False,
        ),
        ModelEntry(
            role="embeddings",
            provider=DEFAULT_PROVIDER,
            model="nomic-embed-text",
            context=2048,
            max_tokens=0,
            timeout=30.0,
            enabled=True,
            allow_cloud=False,
            allowed_tools=frozenset(),
            is_agent_primary=False,
        ),
    )


class ModelRegistry:
    """Registro em memória de modelos locais."""

    def __init__(self, entries: Iterable[ModelEntry] | None = None) -> None:
        items = tuple(entries) if entries is not None else default_entries()
        self._by_role: dict[ModelRole, ModelEntry] = {}
        self._by_model: dict[str, ModelEntry] = {}
        for entry in items:
            validate_model_entry(entry)
            if entry.role in self._by_role:
                raise ConfigurationError(f"role duplicada no registry: {entry.role!r}")
            self._by_role[entry.role] = entry
            self._by_model[entry.model] = entry

    @classmethod
    def default(cls) -> ModelRegistry:
        return cls(default_entries())

    def list_roles(self) -> list[ModelRole]:
        return sorted(self._by_role.keys())

    def list_enabled(self) -> list[ModelEntry]:
        return [entry for entry in self._by_role.values() if entry.enabled]

    def get(self, role: ModelRole) -> ModelEntry:
        try:
            return self._by_role[role]
        except KeyError as exc:
            raise ModelNotFoundError(f"modelo não registrado para role {role!r}") from exc

    def get_by_model(self, model: str) -> ModelEntry:
        name = model.strip()
        try:
            return self._by_model[name]
        except KeyError as exc:
            raise ModelNotFoundError(f"modelo não encontrado: {name!r}") from exc

    def primary_for_intent(self, intent: str) -> ModelEntry:
        """Mapeia intenção do classificador para role do registry."""

        mapping: Mapping[str, ModelRole] = {
            "general": "general",
            "coding": "coder",
            "knowledge": "general",
            "automation": "general",
        }
        role = mapping.get(intent)
        if role is None:
            raise ModelNotFoundError(f"intenção sem modelo no registry: {intent!r}")
        entry = self.get(role)
        if not entry.enabled:
            raise ModelNotFoundError(f"modelo desabilitado para role {role!r}")
        return entry

    def fallback_entry(self) -> ModelEntry:
        entry = self.get("fallback")
        if not entry.enabled:
            raise ModelNotFoundError("modelo de fallback desabilitado")
        if entry.allow_cloud:
            raise SafetyViolationError("fallback não pode ter allow_cloud=true")
        return entry

    def register(self, entry: ModelEntry) -> None:
        validate_model_entry(entry)
        self._by_role[entry.role] = entry
        self._by_model[entry.model] = entry


def validate_model_entry(entry: ModelEntry) -> None:
    """Regras de segurança do registry."""

    if entry.allow_cloud:
        raise SafetyViolationError(
            f"modelo {entry.model!r} não pode ter allow_cloud=true"
        )
    if entry.provider not in {"ollama", "local"}:
        raise SafetyViolationError(
            f"provider não local: {entry.provider!r}"
        )
    if entry.context < 1:
        raise ConfigurationError("context deve ser >= 1")
    if entry.max_tokens < 0:
        raise ConfigurationError("max_tokens deve ser >= 0")
    if entry.timeout <= 0:
        raise ConfigurationError("timeout deve ser > 0")
    if not entry.model.strip():
        raise ConfigurationError("model não pode ser vazio")

    folded = entry.model.casefold()
    if entry.is_agent_primary and any(marker in folded for marker in UNCENSORED_MARKERS):
        raise SafetyViolationError(
            f"modelo uncensored não pode ser agente principal: {entry.model!r}"
        )

    unknown_tools = sorted(entry.allowed_tools - ALLOWED_TOOLS)
    if unknown_tools:
        raise SafetyViolationError(
            "ferramentas fora do registry: " + ", ".join(unknown_tools)
        )
