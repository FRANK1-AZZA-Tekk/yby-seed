"""Registro de tools allowlisted para o loop P0.

Toda chamada passa pela política versionada (`src/safety/agent_policy`):
autonomous roda, manual exige `approve`, human_only nunca roda.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from src.agent_loop.schemas import EchoArgs, VaultSearchArgs, format_validation_error
from src.memory.vault import Vault, VaultError
from src.safety.agent_policy import AgentPolicy, load_agent_policy
from src.safety.policy import Decision

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[BaseModel], dict[str, Any]]


@dataclass(frozen=True)
class ApprovalRequest:
    """O que o humano aprova: tool, argumentos já validados e a decisão da política."""

    tool: str
    arguments: dict[str, Any]
    decision: Decision


Approver = Callable[[ApprovalRequest], bool]


@dataclass(frozen=True, eq=False)
class AuthorizedCall:
    """Autorização de uso único emitida por `ToolRegistry.authorize`."""

    tool: str
    decision: Decision
    _spec: ToolSpec = field(repr=False)
    _parsed: BaseModel = field(repr=False)


class ToolRegistry:
    def __init__(
        self,
        *,
        policy: AgentPolicy | None = None,
        approve: Approver | None = None,
    ) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._policy = policy if policy is not None else load_agent_policy()
        self._approve = approve
        self._issued: set[AuthorizedCall] = set()
        self._lock = threading.Lock()

    @property
    def policy(self) -> AgentPolicy:
        return self._policy

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

    def authorize(self, name: str, arguments: dict[str, Any]) -> AuthorizedCall:
        """Valida e decide sem executar. Recusa levanta `PermissionError`."""

        if name not in self._tools:
            raise KeyError(f"tool não allowlisted: {name}")
        spec = self._tools[name]
        decision = self._policy.decide(name)
        if decision.action == "refuse":
            raise PermissionError(f"tool {name!r} recusada: {decision.reason}")
        try:
            parsed = spec.args_model.model_validate(arguments)
        except ValidationError as exc:
            raise ValueError(format_validation_error(exc)) from exc
        if decision.action == "ask":
            if self._approve is None:
                raise PermissionError(
                    f"tool {name!r} exige aprovação humana e não há canal de confirmação"
                )
            request = ApprovalRequest(name, parsed.model_dump(), decision)
            if self._approve(request) is not True:
                raise PermissionError(f"tool {name!r} não aprovada")
        call = AuthorizedCall(tool=name, decision=decision, _spec=spec, _parsed=parsed)
        with self._lock:
            self._issued.add(call)
        return call

    def execute(self, call: AuthorizedCall) -> dict[str, Any]:
        """Executa uma autorização deste registry, no máximo uma vez."""

        with self._lock:
            if call not in self._issued:
                raise PermissionError("autorização inválida ou já usada")
            self._issued.discard(call)
        return call._spec.handler(call._parsed)

    def run(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.execute(self.authorize(name, arguments))


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
    policy: AgentPolicy | None = None,
    approve: Approver | None = None,
) -> ToolRegistry:
    registry = ToolRegistry(policy=policy, approve=approve)
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


def vault_registry_or_skip(
    *,
    policy: AgentPolicy | None = None,
    approve: Approver | None = None,
) -> ToolRegistry:
    """CLI: vault se configurado; senão só echo_json."""

    from src.memory.vault import vault_from_env

    try:
        vault = vault_from_env()
    except VaultError:
        return default_tool_registry(
            vault=None, include_vault=False, policy=policy, approve=approve
        )
    return default_tool_registry(vault=vault, include_vault=True, policy=policy, approve=approve)