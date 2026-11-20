"""Planner develop — Ollama local ou fila scriptada (testes). Sem nuvem."""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Protocol

from src.develop.schemas import DevelopPlan, Layer
from src.develop.validate import PlanValidationError, validate_plan
from src.engine.providers import OllamaProvider, ProviderError, TextProvider

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

SYSTEM = (
    "Você planeja trabalho em camadas para o YBY SEED (PT-BR). "
    "Responda APENAS com JSON: "
    '{"id":"slug","layers":[{"id":"L1","depends_on":[],"objetivo":"...",'
    '"allowed_files":["src/..."],"non_goals":[],"acceptance":[],'
    '"verification":[]}]}. '
    "Paths relativos ao repo; sem .env, vault/ ou .. . "
    "Sem nuvem. Sem patch aplicável."
)


class DevelopPlanner(Protocol):
    def plan(self, pedido: str, *, repo_root, base_commit: str) -> DevelopPlan: ...


class ScriptedDevelopPlanner:
    """Fila fixa de planos (testes)."""

    def __init__(self, plans: list[DevelopPlan]) -> None:
        self._plans = list(plans)

    def plan(self, pedido: str, *, repo_root, base_commit: str) -> DevelopPlan:
        if not self._plans:
            raise PlanValidationError("fila de planos vazia")
        plan = self._plans.pop(0)
        plan.pedido = pedido
        plan.base_commit = base_commit
        validate_plan(plan, repo_root=repo_root)
        return plan


class OllamaDevelopPlanner:
    def __init__(
        self,
        provider: TextProvider,
        *,
        model: str,
    ) -> None:
        self._provider = provider
        self._model = model

    def plan(self, pedido: str, *, repo_root, base_commit: str) -> DevelopPlan:
        try:
            raw = self._provider.complete(
                pedido,
                model=self._model,
                system=SYSTEM,
            )
        except ProviderError as exc:
            raise PlanValidationError(f"Ollama falhou (sem nuvem): {exc}") from exc
        data = _parse_json(raw)
        plan = _coerce_plan(data, pedido=pedido, base_commit=base_commit)
        validate_plan(plan, repo_root=repo_root)
        return plan


def _parse_json(text: str) -> dict:
    body = text.strip()
    match = _JSON_FENCE.search(body)
    if match:
        body = match.group(1).strip()
    start = body.find("{")
    end = body.rfind("}")
    if start < 0 or end <= start:
        raise PlanValidationError("resposta do planner sem JSON de objeto")
    try:
        data = json.loads(body[start : end + 1])
    except json.JSONDecodeError as exc:
        raise PlanValidationError(f"JSON inválido: {exc}") from exc
    if not isinstance(data, dict):
        raise PlanValidationError("JSON raiz deve ser objeto")
    return data


def _coerce_plan(data: dict, *, pedido: str, base_commit: str) -> DevelopPlan:
    plan_id = str(data.get("id") or f"plan-{uuid.uuid4().hex[:8]}")
    layers_raw = data.get("layers") or []
    if not isinstance(layers_raw, list):
        raise PlanValidationError("layers deve ser lista")
    layers: list[Layer] = []
    for item in layers_raw:
        if not isinstance(item, dict):
            continue
        layers.append(
            Layer(
                id=str(item["id"]),
                depends_on=[str(x) for x in (item.get("depends_on") or [])],
                objetivo=str(item.get("objetivo") or item.get("goal") or ""),
                allowed_files=[str(x) for x in (item.get("allowed_files") or [])],
                non_goals=[str(x) for x in (item.get("non_goals") or [])],
                acceptance=[str(x) for x in (item.get("acceptance") or [])],
                verification=[str(x) for x in (item.get("verification") or [])],
                status="preparada",
                optional_patch=(
                    str(item["optional_patch"])
                    if item.get("optional_patch") is not None
                    else None
                ),
            )
        )
    return DevelopPlan(
        id=plan_id,
        pedido=pedido,
        base_commit=base_commit,
        updated_at=time.time(),
        layers=layers,
    )


def make_ollama_planner() -> OllamaDevelopPlanner:
    from src.engine.config import EngineConfig

    cfg = EngineConfig.from_env()
    return OllamaDevelopPlanner(
        OllamaProvider(cfg.ollama_base_url, timeout=cfg.ollama_timeout),
        model=cfg.local_model,
    )
