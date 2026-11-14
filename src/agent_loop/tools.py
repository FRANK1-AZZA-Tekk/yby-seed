"""Registro de tools allowlisted para o loop P0."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from src.agent_loop.schemas import EchoArgs, VaultSearchArgs, format_validation_error
from src.memory.vault import Vault, VaultError

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[BaseModel], dict[str, Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def names(self) -> list[str]:
        return sorted(self._tools)

    def describe_for_prompt(self) -> str:
        lines = []
        for name in self.names():
            spec = self._tools[name]
            lines.append(f"- {name}: {spec.description}")
        return "\n".join(lines)

    def run(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            raise KeyError(f"tool não allowlisted: {name}")
        spec = self._tools[name]
        try:
            parsed = spec.args_model.model_validate(arguments)
        except ValidationError as exc:
            raise ValueError(format_validation_error(exc)) from exc
        return spec.handler(parsed)


def _echo_handler(args: EchoArgs) -> dict[str, Any]:
    return {"ok": True, "message": args.message}


def _vault_search_handler_factory(vault: Vault) -> Callable[[BaseModel], dict[str, Any]]:
    def handler(args: BaseModel) -> dict[str, Any]:
        assert isinstance(args, VaultSearchArgs)
        hits = vault.search(args.query, k=args.k)
        return {
            "ok": True,
            "hits": [{"name": h.name, "score": round(h.score, 4)} for h in hits],
        }

    return handler


def default_tool_registry(
    *,
    vault: Vault | None = None,
    include_vault: bool = True,
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="echo_json",
            description="Devolve JSON validado com a mensagem (teste e demos).",
            args_model=EchoArgs,
            handler=_echo_handler,
        )
    )
    if include_vault and vault is not None:
        registry.register(
            ToolSpec(
                name="vault_search",
                description="Busca notas no vault (somente leitura).",
                args_model=VaultSearchArgs,
                handler=_vault_search_handler_factory(vault),
            )
        )
    return registry


def vault_registry_or_skip() -> ToolRegistry:
    """CLI: vault se configurado; senão só echo_json."""

    from src.memory.vault import vault_from_env

    try:
        vault = vault_from_env()
    except VaultError:
        return default_tool_registry(vault=None, include_vault=False)
    return default_tool_registry(vault=vault, include_vault=True)