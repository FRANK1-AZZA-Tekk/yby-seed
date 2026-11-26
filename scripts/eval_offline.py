#!/usr/bin/env python3
"""Avaliação offline pt-BR do pipeline YBY (ferramenta de desenvolvimento, fora do `ask`).

Uso: PYTHONPATH=. python scripts/eval_offline.py [--json] [caminho.json]

Roda cada caso de `evals/ptbr_basico.json` contra o código real do motor, do loop
de agente e da porta de segurança, com provedores fakes e relógio simulado.
Sem rede, nuvem, Ollama ou `.env`: mede o pipeline, não a qualidade do modelo.
Sai com código 1 se algum caso falhar.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Sequence, TextIO

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator  # noqa: E402

from src.actions.runner import run_command  # noqa: E402
from src.agent_loop.loop import ControlledAgentLoop  # noqa: E402
from src.agent_loop.planner import OllamaJsonPlanner  # noqa: E402
from src.agent_loop.tools import default_tool_registry  # noqa: E402
from src.engine.budget import CloudBudget  # noqa: E402
from src.engine.cache import ResponseCache  # noqa: E402
from src.engine.cloud_usage_log import CloudUsageLog  # noqa: E402
from src.engine.config import EngineConfig  # noqa: E402
from src.engine.hybrid import HybridEngine  # noqa: E402
from src.engine.providers import CloudCompletion, ProviderError  # noqa: E402
from src.safety.policy import default_policy_path, load_policy  # noqa: E402

DEFAULT_DATASET = ROOT / "evals" / "ptbr_basico.json"
MODEL_CALL_MS = 250
TOOL_CALL_MS = 5
MAX_AGENT_ITERATIONS = 4

_EXPECT_KEYS: dict[str, tuple[set[str], set[str]]] = {
    "ask": ({"provider"}, {"local_calls", "contains_all", "max_reply_chars"}),
    "agent": (
        {"status"},
        {"planner_calls", "tools_executed", "answer_contains", "abort_contains", "error_contains"},
    ),
    "gate": ({"decision"}, {"runner_calls"}),
}


class EvalDatasetError(ValueError):
    """Conjunto de avaliação malformado; nada é executado."""


class Expect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["local", "cloud", "none"] | None = None
    local_calls: int | None = None
    contains_all: list[str] | None = None
    max_reply_chars: int | None = None
    status: Literal["completed", "aborted", "max_steps", "error"] | None = None
    planner_calls: int | None = None
    tools_executed: list[str] | None = None
    answer_contains: str | None = None
    abort_contains: str | None = None
    error_contains: str | None = None
    decision: Literal["run", "ask", "refuse"] | None = None
    runner_calls: int | None = None


class Fake(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str | None = None
    planner_replies: list[str] | None = None


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: str
    kind: Literal["ask", "agent", "gate"]
    input: str
    fake: Fake
    max_prompt_chars: int
    cloud: Literal[False]
    expect: Expect
    verify: str

    @model_validator(mode="after")
    def _check_kind(self) -> Case:
        required, optional = _EXPECT_KEYS[self.kind]
        given = set(self.expect.model_dump(exclude_none=True))
        missing = required - given
        if missing:
            raise ValueError(f"expect sem {sorted(missing)} para kind {self.kind!r}")
        extra = given - required - optional
        if extra:
            raise ValueError(f"expect com {sorted(extra)} não se aplica a kind {self.kind!r}")
        if self.kind == "ask" and self.fake.reply is None:
            raise ValueError("kind 'ask' exige fake.reply")
        if self.kind == "agent" and not self.fake.planner_replies:
            raise ValueError("kind 'agent' exige fake.planner_replies")
        if self.max_prompt_chars <= 0:
            raise ValueError("max_prompt_chars deve ser positivo")
        return self


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    name: str
    description: str
    admission: dict[str, str]
    cases: list[Case]

    @model_validator(mode="after")
    def _unique_ids(self) -> Dataset:
        if not self.cases:
            raise ValueError("conjunto sem casos")
        dupes = sorted(k for k, n in Counter(c.id for c in self.cases).items() if n > 1)
        if dupes:
            raise ValueError(f"ids duplicados: {dupes}")
        return self


@dataclass
class CaseResult:
    id: str
    category: str
    kind: str
    passed: bool
    checks: dict[str, bool]
    calls: dict[str, int]
    tools_executed: list[str]
    error: str | None
    simulated_latency_ms: int
    prompt_chars: int
    max_prompt_chars: int
    notes: dict[str, Any] = field(default_factory=dict)


def load_dataset(path: Path | str = DEFAULT_DATASET) -> Dataset:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return Dataset.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise EvalDatasetError(f"conjunto inválido em {path}: {exc}") from exc


def load_cases(path: Path | str = DEFAULT_DATASET) -> list[Case]:
    return load_dataset(path).cases


class _FakeLocal:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        self.prompts.append(prompt)
        return self.reply


class _ForbiddenCloud:
    """Sem credencial; qualquer chamada é contada e falha."""

    def __init__(self) -> None:
        self.calls = 0

    def has_credentials(self) -> bool:
        return False

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        return self.complete_detail(prompt, model=model, system=system).text

    def complete_detail(self, prompt: str, *, model: str, system: str) -> CloudCompletion:
        self.calls += 1
        raise ProviderError("nuvem proibida na avaliação offline")


class _FakePlannerProvider:
    def __init__(self, replies: Sequence[str]) -> None:
        self._replies = list(replies)
        self.prompt_sizes: list[int] = []

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        self.prompt_sizes.append(len(system) + len(prompt))
        if len(self.prompt_sizes) > len(self._replies):
            raise ProviderError("roteiro do planner esgotado")
        return self._replies[len(self.prompt_sizes) - 1]


def _offline_engine_config() -> EngineConfig:
    base = EngineConfig.from_env(environ={})
    return dataclasses.replace(
        base,
        ollama_base_url="http://ollama.invalid",
        cloud_api_key="",
        cloud_fallback_api_key="",
        cache_ttl_seconds=0.0,
    )


def _run_ask(case: Case) -> CaseResult:
    expect = case.expect
    local = _FakeLocal(case.fake.reply or "")
    cloud = _ForbiddenCloud()
    with tempfile.TemporaryDirectory(prefix="yby-eval-") as tmp:
        log_path = Path(tmp) / "cloud.jsonl"
        budget = CloudBudget(
            cloud_mode="local_only",
            log_path=log_path,
            daily_token_limit=0,
            warn_daily_token_limit=0,
            monthly_token_limit=0,
            warn_token_limit=0,
            require_confirm=True,
            allow_no_tty=False,
        )
        engine = HybridEngine(
            _offline_engine_config(),
            local,
            cloud,
            cache=ResponseCache(ttl_seconds=0),
            cloud_log=CloudUsageLog(log_path),
            budget=budget,
            confirm_fn=lambda _msg: False,
            has_tty_fn=lambda: False,
        )
        reply = engine.reply(case.input)
    text = reply.text.casefold()
    prompt_chars = max((len(p) for p in local.prompts), default=len(case.input))
    checks = {
        "provider": reply.provider == expect.provider,
        "cloud_calls_zero": cloud.calls == 0,
        "prompt_within_limit": prompt_chars <= case.max_prompt_chars,
    }
    if expect.local_calls is not None:
        checks["local_calls"] = len(local.prompts) == expect.local_calls
    if expect.contains_all is not None:
        checks["contains_all"] = all(term.casefold() in text for term in expect.contains_all)
    if expect.max_reply_chars is not None:
        checks["max_reply_chars"] = len(reply.text) <= expect.max_reply_chars
    return CaseResult(
        id=case.id,
        category=case.category,
        kind=case.kind,
        passed=all(checks.values()),
        checks=checks,
        calls={"local": len(local.prompts), "cloud": cloud.calls, "planner": 0, "runner": 0},
        tools_executed=[],
        error=reply.notice if reply.provider == "none" else None,
        simulated_latency_ms=MODEL_CALL_MS * len(local.prompts),
        prompt_chars=prompt_chars,
        max_prompt_chars=case.max_prompt_chars,
        notes={"route_reasons": list(reply.reasons)},
    )


def _run_agent(case: Case) -> CaseResult:
    expect = case.expect
    provider = _FakePlannerProvider(case.fake.planner_replies or [])
    planner = OllamaJsonPlanner(
        provider,
        model=_offline_engine_config().local_model,
        planner_json_format=False,
        prompt_max_chars=case.max_prompt_chars,
    )
    loop = ControlledAgentLoop(
        registry=default_tool_registry(include_vault=False),
        planner=planner,
        max_iterations=MAX_AGENT_ITERATIONS,
        tool_timeout_seconds=None,
    )
    result = loop.run(case.input)
    tools = [
        str(step.detail.get("name"))
        for step in result.steps
        if step.kind == "tool" and step.error is None and "result" in step.detail
    ]
    error = next((step.error for step in result.steps if step.error), None)
    prompt_chars = max(provider.prompt_sizes, default=0)
    checks = {
        "status": result.status == expect.status,
        "cloud_calls_zero": True,
        "prompt_within_limit": prompt_chars <= case.max_prompt_chars,
    }
    if expect.planner_calls is not None:
        checks["planner_calls"] = len(provider.prompt_sizes) == expect.planner_calls
    if expect.tools_executed is not None:
        checks["tools_executed"] = tools == expect.tools_executed
    if expect.answer_contains is not None:
        answer = json.dumps(result.final_answer, ensure_ascii=False) if result.final_answer else ""
        checks["answer_contains"] = expect.answer_contains in answer
    if expect.abort_contains is not None:
        checks["abort_contains"] = expect.abort_contains in (result.abort_reason or "")
    if expect.error_contains is not None:
        checks["error_contains"] = expect.error_contains in (error or "")
    return CaseResult(
        id=case.id,
        category=case.category,
        kind=case.kind,
        passed=all(checks.values()),
        checks=checks,
        calls={"local": 0, "cloud": 0, "planner": len(provider.prompt_sizes), "runner": 0},
        tools_executed=tools,
        error=error,
        simulated_latency_ms=MODEL_CALL_MS * len(provider.prompt_sizes) + TOOL_CALL_MS * len(tools),
        prompt_chars=prompt_chars,
        max_prompt_chars=case.max_prompt_chars,
        notes={"status": result.status, "abort_reason": result.abort_reason},
    )


def _run_gate(case: Case) -> CaseResult:
    expect = case.expect
    runner_calls: list[Sequence[str]] = []

    def fake_runner(argv: Sequence[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        runner_calls.append(list(argv))
        return subprocess.CompletedProcess(list(argv), 0, stdout="", stderr="")

    result = run_command(
        case.input,
        policy=load_policy(default_policy_path()),
        project_root=ROOT,
        input_fn=lambda: "n",
        output_fn=lambda _msg: None,
        runner=fake_runner,
    )
    prompt_chars = len(case.input)
    checks = {
        "decision": result.decision.action == expect.decision,
        "cloud_calls_zero": True,
        "prompt_within_limit": prompt_chars <= case.max_prompt_chars,
    }
    if expect.runner_calls is not None:
        checks["runner_calls"] = len(runner_calls) == expect.runner_calls
    return CaseResult(
        id=case.id,
        category=case.category,
        kind=case.kind,
        passed=all(checks.values()),
        checks=checks,
        calls={"local": 0, "cloud": 0, "planner": 0, "runner": len(runner_calls)},
        tools_executed=[],
        error=None,
        simulated_latency_ms=0,
        prompt_chars=prompt_chars,
        max_prompt_chars=case.max_prompt_chars,
        notes={"decision": result.decision.action, "reason": result.decision.reason},
    )


_RUNNERS = {"ask": _run_ask, "agent": _run_agent, "gate": _run_gate}


def run_case(case: Case) -> CaseResult:
    try:
        return _RUNNERS[case.kind](case)
    except Exception as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        return CaseResult(
            id=case.id,
            category=case.category,
            kind=case.kind,
            passed=False,
            checks={"exception": False},
            calls={"local": 0, "cloud": 0, "planner": 0, "runner": 0},
            tools_executed=[],
            error=f"{type(exc).__name__}: {exc}",
            simulated_latency_ms=0,
            prompt_chars=0,
            max_prompt_chars=case.max_prompt_chars,
        )


def run_all(path: Path | str = DEFAULT_DATASET) -> dict[str, Any]:
    dataset = load_dataset(path)
    results = [run_case(case) for case in dataset.cases]
    passed = sum(1 for r in results if r.passed)
    return {
        "dataset": dataset.name,
        "version": dataset.version,
        "totals": {
            "cases": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "cloud_calls": sum(r.calls["cloud"] for r in results),
            "tools_executed": sum(len(r.tools_executed) for r in results),
            "simulated_latency_ms": sum(r.simulated_latency_ms for r in results),
        },
        "cases": [asdict(r) for r in results],
    }


def _summary_line(case: dict[str, Any]) -> str:
    calls = case["calls"]
    status = "PASS" if case["passed"] else "FAIL"
    failed = [name for name, ok in case["checks"].items() if not ok]
    line = (
        f"{status} {case['id']} [{case['category']}] "
        f"local={calls['local']} planner={calls['planner']} cloud={calls['cloud']} "
        f"runner={calls['runner']} tools={case['tools_executed']} "
        f"{case['simulated_latency_ms']}ms"
    )
    if failed:
        line += f" falhou={failed}"
    if case["error"] and not case["passed"]:
        line += f" erro={case['error']}"
    return line


def main(argv: Sequence[str] | None = None, *, out: TextIO | None = None) -> int:
    stream = out if out is not None else sys.stdout
    parser = argparse.ArgumentParser(description="Avaliação offline pt-BR do pipeline YBY.")
    parser.add_argument("dataset", nargs="?", default=str(DEFAULT_DATASET))
    parser.add_argument("--json", action="store_true", help="relatório completo em JSON")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        report = run_all(args.dataset)
    except EvalDatasetError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    if args.json:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    else:
        for case in report["cases"]:
            stream.write(_summary_line(case) + "\n")
        totals = report["totals"]
        stream.write(
            f"total: {totals['passed']}/{totals['cases']} ok, nuvem={totals['cloud_calls']}, "
            f"tools={totals['tools_executed']}, latência simulada={totals['simulated_latency_ms']}ms\n"
        )
    return 0 if report["totals"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
