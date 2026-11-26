"""Política versionada das tools do agente. Decide; não executa nada."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping

import yaml

from src.safety.policy import Decision

Autonomy = Literal["autonomous", "manual", "human_only"]
Risk = Literal["read", "write", "external", "privileged"]

POLICY_VERSION = 1
AUTONOMY_LEVELS: frozenset[str] = frozenset({"autonomous", "manual", "human_only"})
RISK_LEVELS: frozenset[str] = frozenset({"read", "write", "external", "privileged"})
_DEFAULT_LEVELS = frozenset({"manual", "human_only"})
_TOP_KEYS = frozenset({"version", "default", "actions"})
_RULE_KEYS = frozenset({"autonomy", "risk", "description"})
_ACTION_ID = re.compile(r"^[a-z][a-z0-9_.]*$")
_TO_DECISION = {"autonomous": "run", "manual": "ask", "human_only": "refuse"}


class AgentPolicyError(ValueError):
    """Política ausente ou inválida: nenhuma tool deve executar."""


@dataclass(frozen=True)
class ActionRule:
    autonomy: Autonomy
    risk: Risk
    description: str


@dataclass(frozen=True)
class AgentPolicy:
    version: int
    default: Autonomy
    actions: Mapping[str, ActionRule]

    def decide(self, action_id: str) -> Decision:
        rule = self.actions.get(action_id)
        if rule is None:
            return Decision(
                _TO_DECISION[self.default], f"sem entrada na política: padrão {self.default}"
            )
        return Decision(_TO_DECISION[rule.autonomy], f"política: {rule.autonomy} ({rule.risk})")


def default_agent_policy_path() -> Path:
    """Arquivo versionado na raiz do repositório."""

    return Path(__file__).resolve().parents[2] / "config" / "agent-policy.yaml"


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode) -> dict:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in mapping:
            raise AgentPolicyError(f"chave duplicada: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=True)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def load_agent_policy(path: Path | None = None) -> AgentPolicy:
    """Lê e valida a política. Qualquer problema levanta `AgentPolicyError`."""

    source = path if path is not None else default_agent_policy_path()
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise AgentPolicyError(f"política ilegível em {source}: {exc}") from exc
    return parse_agent_policy(text)


def parse_agent_policy(text: str) -> AgentPolicy:
    try:
        data = yaml.load(text, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise AgentPolicyError(f"YAML inválido: {exc}") from exc
    if not isinstance(data, dict):
        raise AgentPolicyError("a política deve ser um mapeamento")
    if set(data) != _TOP_KEYS:
        raise AgentPolicyError(f"chaves de topo devem ser {sorted(_TOP_KEYS)}")

    version = data["version"]
    if isinstance(version, bool) or version != POLICY_VERSION:
        raise AgentPolicyError(f"versão não suportada: {version!r}")
    default = data["default"]
    if default not in _DEFAULT_LEVELS:
        raise AgentPolicyError(f"default deve ser manual ou human_only, não {default!r}")

    raw_actions = data["actions"]
    if not isinstance(raw_actions, dict) or not raw_actions:
        raise AgentPolicyError("actions deve ser um mapeamento não vazio")
    actions = {
        action_id: _parse_rule(action_id, raw) for action_id, raw in raw_actions.items()
    }
    return AgentPolicy(
        version=version, default=default, actions=MappingProxyType(actions)
    )


def _parse_rule(action_id: object, raw: object) -> ActionRule:
    if not isinstance(action_id, str) or not _ACTION_ID.match(action_id):
        raise AgentPolicyError(f"id de ação inválido: {action_id!r}")
    if not isinstance(raw, dict) or set(raw) != _RULE_KEYS:
        raise AgentPolicyError(f"{action_id}: campos devem ser {sorted(_RULE_KEYS)}")
    autonomy, risk, description = raw["autonomy"], raw["risk"], raw["description"]
    if autonomy not in AUTONOMY_LEVELS:
        raise AgentPolicyError(f"{action_id}: autonomy inválida {autonomy!r}")
    if risk not in RISK_LEVELS:
        raise AgentPolicyError(f"{action_id}: risk inválido {risk!r}")
    if not isinstance(description, str) or not description.strip():
        raise AgentPolicyError(f"{action_id}: description vazia")
    if autonomy == "autonomous" and risk != "read":
        raise AgentPolicyError(f"{action_id}: só risk read pode ser autonomous")
    if risk == "privileged" and autonomy != "human_only":
        raise AgentPolicyError(f"{action_id}: risk privileged exige human_only")
    return ActionRule(autonomy=autonomy, risk=risk, description=description.strip())
