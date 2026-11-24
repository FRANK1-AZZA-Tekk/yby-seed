"""Projeção do histórico para o prompt do OllamaJsonPlanner (caracteres, não tokens)."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
OMITTED_STEPS_KEY = "_yby_planner_omitted_steps"
PLANNER_NOTE_KEY = "_yby_planner_note"
REDUCED_OBSERVATION_MARKER = "…[observação reduzida pelo limite do planner]…"


class PlannerPromptTooLargeError(ValueError):
    """Tarefa/tools obrigatórios não cabem no teto; falha antes do provedor."""


def planner_prompt_total_chars(*, system: str, user_prompt: str) -> int:
    return len(system) + len(user_prompt)


def _history_json_text(items: Sequence[Mapping[str, object]]) -> str:
    return json.dumps(list(items), ensure_ascii=False, separators=(",", ":"))


def _truncate_observation_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    marker = REDUCED_OBSERVATION_MARKER
    if max_chars <= len(marker):
        return marker[:max_chars]
    keep = max_chars - len(marker)
    return text[:keep] + marker


def _shrink_value(value: object, max_str: int) -> object:
    if isinstance(value, str):
        return _truncate_observation_text(value, max_str)
    if isinstance(value, dict):
        return {k: _shrink_value(v, max_str) for k, v in value.items()}
    if isinstance(value, list):
        return [_shrink_value(v, max_str) for v in value]
    return value


def _shrink_step_copy(step: Mapping[str, object], *, max_observation_chars: int) -> dict[str, object]:
    out: dict[str, object] = copy.deepcopy(step)
    for key in ("result", "arguments", "error", "answer"):
        if key in out:
            out[key] = _shrink_value(out[key], max_observation_chars)
    return out


def _omission_meta(*, omitted: int, note: str | None = None) -> dict[str, object]:
    meta: dict[str, object] = {OMITTED_STEPS_KEY: omitted}
    if note:
        meta[PLANNER_NOTE_KEY] = note
    return meta


def project_history_json(
    history: Sequence[dict[str, object]],
    *,
    max_history_json_chars: int,
) -> str:
    """Monta um array JSON válido dentro do orçamento, priorizando passos recentes."""

    if max_history_json_chars < 2:
        msg = "orçamento de histórico no prompt é insuficiente para JSON válido"
        raise PlannerPromptTooLargeError(msg)

    items = list(history)
    if not items:
        return "[]"

    full_text = _history_json_text(items)
    if len(full_text) <= max_history_json_chars:
        return full_text

    n = len(items)
    shrink_limits = (50_000, 4_000, 1_000, 400, 160, 64, 24, 8, 0)
    for keep in range(n, 0, -1):
        omitted = n - keep
        recent = items[-keep:]
        for max_obs in shrink_limits:
            projected: list[dict[str, object]] = []
            if omitted:
                projected.append(_omission_meta(omitted=omitted))
            projected.extend(_shrink_step_copy(step, max_observation_chars=max_obs) for step in recent)
            text = _history_json_text(projected)
            if len(text) <= max_history_json_chars:
                return text

    for note in (
        "nenhum passo coube no limite de caracteres do planner",
        "histórico omitido",
    ):
        text = _history_json_text([_omission_meta(omitted=n, note=note)])
        if len(text) <= max_history_json_chars:
            return text

    minimal = _history_json_text([{OMITTED_STEPS_KEY: n}])
    if len(minimal) <= max_history_json_chars:
        return minimal

    msg = "histórico não cabe no orçamento mínimo de caracteres do planner"
    raise PlannerPromptTooLargeError(msg)


def build_planner_user_prompt(
    *,
    system: str,
    task: str,
    tools_blurb: str,
    history: Sequence[dict[str, object]],
    max_total_chars: int,
) -> str:
    """Prompt do usuário com histórico projetado; valida system+prompt."""

    prefix = (
        f"Tarefa: {task}\n\n"
        f"Tools disponíveis:\n{tools_blurb}\n\n"
        f"Histórico de passos (JSON):\n"
    )
    suffix = "\n\nPróximo passo (um JSON):"
    mandatory = planner_prompt_total_chars(
        system=system,
        user_prompt=prefix + "[]" + suffix,
    )
    if mandatory > max_total_chars:
        raise PlannerPromptTooLargeError(
            "conteúdo obrigatório do planner (tarefa, tools e instruções) excede "
            f"o teto configurado ({max_total_chars} caracteres Python, não tokens). "
            "Reduza a tarefa ou a lista de tools."
        )

    history_budget = max_total_chars - len(system) - len(prefix) - len(suffix)
    history_json = project_history_json(history, max_history_json_chars=history_budget)
    prompt = prefix + history_json + suffix
    total = planner_prompt_total_chars(system=system, user_prompt=prompt)
    if total > max_total_chars:
        msg = "projeção do histórico excedeu o teto do prompt do planner"
        raise PlannerPromptTooLargeError(msg)
    return prompt