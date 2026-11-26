"""Contrato de idempotência de tools com efeito externo (offline; sem I/O nem rede)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from src.agent_loop.idempotency import (
    DEFAULT_WINDOW_SECONDS,
    IdempotencyError,
    InMemoryOperationLedger,
    OperationExists,
    Outcome,
    normalize_arguments,
    operation_id,
    requires_idempotency,
    run_once,
)
from src.safety.agent_policy import (
    ActionRule,
    AgentPolicyError,
    load_agent_policy,
    parse_agent_policy,
)

ACTION = "note.write"
TARGET = "vault:inbox/a.md"
ARGS = {"title": "Olá", "tags": ["x", "y"]}
VECTOR = "8895451242b39e9fb711a9a1702ce6550f19ae516de551e068a4715e224f7840"


class _Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def _ledger() -> tuple[InMemoryOperationLedger, _Clock]:
    clock = _Clock()
    return InMemoryOperationLedger(clock=clock), clock


def _op() -> str:
    return operation_id(ACTION, TARGET, ARGS)


# a) operation_id determinístico
def test_operation_id_is_deterministic_and_pinned():
    assert _op() == _op() == VECTOR


# b) argumentos equivalentes geram o mesmo ID
def test_equivalent_arguments_same_id():
    nfd = {"title": "Ola\u0301", "tags": ("x", "y")}
    assert operation_id(ACTION, TARGET, nfd) == VECTOR

    class Args(BaseModel):
        title: str
        tags: list[str]

    assert operation_id(ACTION, TARGET, Args(**ARGS)) == VECTOR


@pytest.mark.parametrize(
    "action,target,args",
    [
        ("note.append", TARGET, ARGS),
        (ACTION, "vault:inbox/b.md", ARGS),
        (ACTION, TARGET, {"title": "Olá!", "tags": ["x", "y"]}),
        (ACTION, TARGET, {"title": "Olá", "tags": ["x", "y"], "extra": None}),
    ],
)
def test_different_operation_different_id(action, target, args):
    assert operation_id(action, target, args) != VECTOR


# c) ordem diferente não altera ID quando semanticamente equivalente
def test_key_order_does_not_change_id():
    assert operation_id(ACTION, TARGET, {"tags": ["x", "y"], "title": "Olá"}) == VECTOR
    nested_a = {"meta": {"a": 1, "b": 2}}
    nested_b = {"meta": {"b": 2, "a": 1}}
    assert operation_id(ACTION, TARGET, nested_a) == operation_id(ACTION, TARGET, nested_b)


def test_list_order_matters_unless_declared_unordered():
    swapped = {"title": "Olá", "tags": ["y", "x"]}
    assert operation_id(ACTION, TARGET, swapped) != VECTOR
    unordered = frozenset({"tags"})
    assert operation_id(ACTION, TARGET, swapped, unordered=unordered) == operation_id(
        ACTION, TARGET, ARGS, unordered=unordered
    )


# d) falha não é tratada como sucesso
def test_explicit_failure_recorded_as_failed():
    ledger, _ = _ledger()
    record = run_once(ledger, ACTION, _op(), lambda: Outcome("failed", "remote_rejected"))
    assert record.status == "failed"
    assert record.error_code == "remote_rejected"
    assert ledger.lookup(_op()).status == "failed"


def test_success_only_from_explicit_outcome():
    ledger, _ = _ledger()
    assert run_once(ledger, ACTION, _op(), lambda: Outcome("succeeded")).status == "succeeded"
    with pytest.raises(IdempotencyError):
        Outcome("succeeded", "oops")
    with pytest.raises(IdempotencyError):
        Outcome("unknown")  # type: ignore[arg-type]


# e) incerteza vira unknown
@pytest.mark.parametrize("value", [None, True, {"ok": True}, "succeeded"])
def test_ambiguous_return_is_unknown(value):
    ledger, _ = _ledger()
    assert run_once(ledger, ACTION, _op(), lambda: value).status == "unknown"


def test_exception_is_unknown_not_failed():
    ledger, _ = _ledger()

    def boom() -> Outcome:
        raise TimeoutError("sem resposta do remoto")

    record = run_once(ledger, ACTION, _op(), boom)
    assert record.status == "unknown"
    assert record.error_code is None


def test_interrupt_marks_unknown_and_propagates():
    ledger, _ = _ledger()

    def interrupted() -> Outcome:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_once(ledger, ACTION, _op(), interrupted)
    assert ledger.lookup(_op()).status == "unknown"


def test_recover_turns_pending_into_unknown():
    ledger, _ = _ledger()
    ledger.begin(_op(), ACTION)
    assert ledger.recover() == 1
    assert ledger.lookup(_op()).status == "unknown"


def test_unknown_does_not_expire_and_needs_explicit_resolution():
    ledger, clock = _ledger()
    run_once(ledger, ACTION, _op(), lambda: None)
    clock.now += DEFAULT_WINDOW_SECONDS * 10
    with pytest.raises(OperationExists) as exc:
        ledger.begin(_op(), ACTION)
    assert exc.value.record.status == "unknown"
    resolved = ledger.resolve_unknown(_op(), Outcome("succeeded"))
    assert resolved.status == "succeeded"


# f) sem retry automático
@pytest.mark.parametrize(
    "first",
    [lambda: Outcome("succeeded"), lambda: Outcome("failed", "boom"), lambda: None],
)
def test_second_run_does_not_call_effect(first):
    ledger, _ = _ledger()
    calls: list[int] = []

    def effect() -> object:
        calls.append(1)
        return first()

    status = run_once(ledger, ACTION, _op(), effect).status
    with pytest.raises(OperationExists) as exc:
        run_once(ledger, ACTION, _op(), effect)
    assert exc.value.record.status == status
    assert calls == [1]


def test_pending_blocks_concurrent_repeat():
    ledger, _ = _ledger()
    ledger.begin(_op(), ACTION)
    calls: list[int] = []
    with pytest.raises(OperationExists):
        run_once(ledger, ACTION, _op(), lambda: calls.append(1))
    assert calls == []


def test_new_operation_only_after_window_for_final_states():
    ledger, clock = _ledger()
    run_once(ledger, ACTION, _op(), lambda: Outcome("succeeded"))
    clock.now += DEFAULT_WINDOW_SECONDS - 1
    with pytest.raises(OperationExists):
        ledger.begin(_op(), ACTION)
    clock.now += 1
    assert ledger.begin(_op(), ACTION).status == "pending"


# g) ferramentas puras/leitura não exigem idempotência
def test_read_tools_do_not_require_idempotency():
    assert not requires_idempotency(ActionRule("autonomous", "read", "leitura"))
    policy = load_agent_policy()
    for name in ("echo_json", "vault_search"):
        assert not requires_idempotency(policy.actions[name])


# h) ferramenta mutável futura exige política manual
@pytest.mark.parametrize("risk", ["write", "external", "privileged"])
def test_mutable_tools_require_idempotency(risk):
    assert requires_idempotency(ActionRule("manual", risk, "efeito"))


@pytest.mark.parametrize("risk", ["write", "external"])
def test_policy_rejects_autonomous_mutable_tool(risk):
    text = (
        "version: 1\ndefault: manual\nactions:\n"
        f"  note.write:\n    autonomy: autonomous\n    risk: {risk}\n"
        '    description: "efeito"\n'
    )
    with pytest.raises(AgentPolicyError, match="autonomous"):
        parse_agent_policy(text)


def test_unlisted_future_tool_defaults_to_manual_and_requires_idempotency():
    policy = load_agent_policy()
    assert "note.write" not in policy.actions
    assert policy.decide("note.write").action == "ask"
    assert requires_idempotency(policy.actions.get("note.write"))


# entradas inválidas
@pytest.mark.parametrize(
    "action,target,args",
    [
        ("", TARGET, ARGS),
        ("Note.Write", TARGET, ARGS),
        (ACTION, "", ARGS),
        (ACTION, "   ", ARGS),
        (ACTION, TARGET, {"x": float("nan")}),
        (ACTION, TARGET, {"x": float("inf")}),
        (ACTION, TARGET, {1: "chave"}),
        (ACTION, TARGET, {"x": object()}),
        (ACTION, TARGET, ["não", "mapa"]),
    ],
)
def test_invalid_input_rejected(action, target, args):
    with pytest.raises(IdempotencyError):
        operation_id(action, target, args)


def test_equivalent_duplicate_keys_rejected():
    with pytest.raises(IdempotencyError):
        normalize_arguments({"Ola\u0301": 1, "Olá": 2})


def test_forbidden_transitions():
    ledger, _ = _ledger()
    op = _op()
    with pytest.raises(IdempotencyError):
        ledger.finish(op, Outcome("succeeded"))
    ledger.begin(op, ACTION)
    with pytest.raises(IdempotencyError):
        ledger.finish(op, {"status": "succeeded"})  # type: ignore[arg-type]
    with pytest.raises(IdempotencyError):
        ledger.resolve_unknown(op, Outcome("succeeded"))
    ledger.finish(op, Outcome("failed", "boom"))
    with pytest.raises(IdempotencyError):
        ledger.mark_unknown(op)
    with pytest.raises(IdempotencyError):
        ledger.begin("nao-hex", ACTION)
    with pytest.raises(IdempotencyError):
        InMemoryOperationLedger(window_seconds=0)


def test_record_keeps_no_arguments_or_target():
    ledger, _ = _ledger()
    record = run_once(ledger, ACTION, _op(), lambda: Outcome("succeeded"))
    dumped = repr(record)
    for secret in ("Olá", "inbox", TARGET, "tags"):
        assert secret not in dumped
