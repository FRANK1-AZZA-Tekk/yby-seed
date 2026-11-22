"""Briefing declarativo: hash de conteúdo não representa autorização."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal

from src.safety.policy import SKILL_ACTIONS, is_allowed_skill_action

ALLOWED_ACTIONS = SKILL_ACTIONS


@dataclass(frozen=True)
class ActionBriefing:
    """Plano imutável, sem execução, persistência ou aprovação implícita.

    Entradas são pares de strings; caminhos e políticas devem ser validados
    pelo planejador antes da confirmação e pelo futuro executor.
    O hash detecta diferenças de conteúdo, não autentica aprovação humana.
    """

    skill_name: str
    request: str
    action: str
    inputs: tuple[tuple[str, str], ...]
    effects: tuple[str, ...]
    risks: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("skill_name", "request", "action"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} deve ser uma string não vazia")
        if not is_allowed_skill_action(self.action):
            raise ValueError(f"Ação não permitida: {self.action!r}")
        if not isinstance(self.inputs, tuple) or not self.inputs:
            raise ValueError("inputs deve ser uma tupla não vazia de pares")
        keys: set[str] = set()
        for pair in self.inputs:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise ValueError("Cada entrada deve ser um par imutável")
            key, value = pair
            if any(not isinstance(item, str) or not item.strip() for item in pair):
                raise ValueError("Entradas exigem chaves e valores não vazios")
            if key in keys:
                raise ValueError(f"Entrada duplicada: {key!r}")
            keys.add(key)
        for name in ("effects", "risks"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{name} deve ser uma tupla não vazia")
            if any(not isinstance(item, str) or not item.strip() for item in values):
                raise ValueError(f"{name} exige strings não vazias")

    @property
    def status(self) -> Literal["pending"]:
        """Aprovação pertence a um registro separado, nunca ao plano."""
        return "pending"

    def canonical_json(self) -> str:
        """Serializa todos os campos aprováveis com versão explícita."""
        return json.dumps(
            {
                "schema_version": 1,
                "skill_name": self.skill_name,
                "request": self.request,
                "action": self.action,
                "inputs": dict(self.inputs),
                "effects": self.effects,
                "risks": self.risks,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def briefing_hash(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @property
    def briefing_id(self) -> str:
        """Identificador determinístico; não é uma credencial."""
        return f"sha256:{self.briefing_hash}"
