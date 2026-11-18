"""Análise de padrões via Ollama local apenas (sem nuvem)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.evo.aggregate import DayAggregate
from src.evo.sanitize import sanitize_text

DEFAULT_SYSTEM = (
    "You are Evo, a local offline analyst for YBY SEED. "
    "Reply with a single JSON object only (no markdown). "
    "Keys: hypotheses (list of {title, rationale, confidence}), "
    "proposals (list of {title, priority, rationale}), "
    "risks (list of strings), next_steps (list of strings). "
    "Do not suggest automatic code application or cloud calls. "
    "priority is an integer 1=highest. Reports only — no Night Watch apply."
)


class TextCompleter(Protocol):
    """Compatível com OllamaProvider.complete."""

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        ...


@dataclass
class AnalysisResult:
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    proposals: list[dict[str, Any]] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    raw_text: str = ""
    used_model: str = ""
    offline_fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypotheses": list(self.hypotheses),
            "proposals": list(self.proposals),
            "risks": list(self.risks),
            "next_steps": list(self.next_steps),
            "used_model": self.used_model,
            "offline_fallback": self.offline_fallback,
        }


def build_analysis_prompt(agg: DayAggregate) -> str:
    """Prompt curto com agregados sanitizados (sem segredos)."""

    payload = {
        "day": agg.day,
        "total": agg.total,
        "by_kind": agg.by_kind,
        "by_severity": agg.by_severity,
        "problems": agg.problems[:20],
        "evidence": agg.evidence[:30],
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return sanitize_text(
        "Analyze this local YBY SEED day aggregate and propose hypotheses.\n"
        f"{body}\n"
        "Remember: reports only; no auto code changes; no cloud."
    )


def _heuristic_analysis(agg: DayAggregate) -> AnalysisResult:
    """Fallback offline se Ollama falhar — ainda gera relatório útil."""

    hypotheses: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    risks: list[str] = []
    next_steps: list[str] = []

    if agg.errors or any("ollama" in p.casefold() for p in agg.problems):
        hypotheses.append(
            {
                "title": "Instabilidade do Ollama local",
                "rationale": "Eventos de erro mencionam Ollama ou provider local.",
                "confidence": 0.6,
            }
        )
        proposals.append(
            {
                "title": "Verificar hub/keepalive e `ollama list`",
                "priority": 1,
                "rationale": "Reduz falhas de ask/agent --local sem sair do offline.",
            }
        )
        risks.append("Relatório sem LLM: hipóteses heurísticas apenas.")
        next_steps.append("Rodar `python yby.py hub --once` e re-gerar o relatório.")

    if agg.by_kind.get("cloud_call"):
        hypotheses.append(
            {
                "title": "Uso de nuvem registado localmente",
                "rationale": "JSONL/eventos cloud_call presentes (só leitura).",
                "confidence": 0.5,
            }
        )
        proposals.append(
            {
                "title": "Rever confirmações D12 e orçamento",
                "priority": 2,
                "rationale": "Cloud calls são evidência local; Evo não chama nuvem.",
            }
        )

    if not hypotheses:
        hypotheses.append(
            {
                "title": "Dia estável",
                "rationale": "Poucos ou nenhum problema listado na agregação.",
                "confidence": 0.4,
            }
        )
        next_steps.append("Continuar a ingerir eventos e comparar dias.")

    if not next_steps:
        next_steps.append("Rever propostas manualmente; Evo v0.1 não aplica patches.")

    risks.append("Evo v0.1 não altera código automaticamente.")
    return AnalysisResult(
        hypotheses=hypotheses,
        proposals=sorted(proposals, key=lambda p: int(p.get("priority") or 99)),
        risks=risks,
        next_steps=next_steps,
        offline_fallback=True,
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def analyze_day(
    agg: DayAggregate,
    *,
    completer: TextCompleter | None,
    model: str,
) -> AnalysisResult:
    """Chama Ollama local se `completer` for dado; senão heurística."""

    if completer is None:
        return _heuristic_analysis(agg)

    prompt = build_analysis_prompt(agg)
    try:
        raw = completer.complete(prompt, model=model, system=DEFAULT_SYSTEM)
    except Exception as exc:  # noqa: BLE001 — fallback offline é o contrato
        result = _heuristic_analysis(agg)
        result.raw_text = sanitize_text(str(exc))
        result.risks = [f"Ollama falhou: {sanitize_text(str(exc))}"] + list(result.risks)
        return result

    raw = sanitize_text(raw)
    parsed = _extract_json(raw)
    if not parsed:
        result = _heuristic_analysis(agg)
        result.raw_text = raw
        result.risks = ["Resposta Ollama não-JSON; usei heurística."] + list(result.risks)
        return result

    hypotheses = parsed.get("hypotheses") or []
    proposals = parsed.get("proposals") or []
    risks = parsed.get("risks") or []
    next_steps = parsed.get("next_steps") or []
    if not isinstance(hypotheses, list):
        hypotheses = []
    if not isinstance(proposals, list):
        proposals = []
    if not isinstance(risks, list):
        risks = [str(risks)]
    if not isinstance(next_steps, list):
        next_steps = [str(next_steps)]

    def _prio(item: Any) -> int:
        if isinstance(item, dict):
            try:
                return int(item.get("priority") or 99)
            except (TypeError, ValueError):
                return 99
        return 99

    proposals_sorted = sorted(
        [p for p in proposals if isinstance(p, dict)],
        key=_prio,
    )
    return AnalysisResult(
        hypotheses=[h for h in hypotheses if isinstance(h, dict)],
        proposals=proposals_sorted,
        risks=[sanitize_text(str(r)) for r in risks],
        next_steps=[sanitize_text(str(s)) for s in next_steps],
        raw_text=raw,
        used_model=model,
        offline_fallback=False,
    )
