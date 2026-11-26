"""Contrato de idempotência para tools com efeito externo (docs/TOOL_IDEMPOTENCY.md).

Referência pura e em memória: não faz I/O e não está ligada ao `ToolRegistry`.
Sucesso só por `Outcome` explícito; o resto vira `unknown`; nunca há retry.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any, Literal

from pydantic import BaseModel

from src.safety.agent_policy import _ACTION_ID, ActionRule

IDEMPOTENCY_VERSION = 1
DEFAULT_WINDOW_SECONDS = 24 * 60 * 60

OperationStatus = Literal["pending", "succeeded", "failed", "unknown"]
FinalStatus = Literal["succeeded", "failed"]

_OPERATION_ID = re.compile(r"^[0-9a-f]{64}$")
_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class IdempotencyError(ValueError):
    """Entrada inválida ou transição de estado proibida."""


def _canonical(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise IdempotencyError("argumento numérico não finito")
        return value
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise IdempotencyError(f"chave não textual: {key!r}")
            norm_key = unicodedata.normalize("NFC", key)
            if norm_key in out:
                raise IdempotencyError(f"chaves equivalentes duplicadas: {key!r}")
            out[norm_key] = _canonical(item)
        return out
    if isinstance(value, list | tuple):
        return [_canonical(item) for item in value]
    raise IdempotencyError(f"tipo de argumento não suportado: {type(value).__name__}")


def _dumps(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def normalize_arguments(
    arguments: Mapping[str, Any] | BaseModel,
    *,
    unordered: frozenset[str] = frozenset(),
) -> str:
    """JSON canônico dos argumentos já validados.

    Ordem de chaves não importa; ordem de listas importa, exceto nos campos de
    topo declarados em `unordered`.
    """

    raw = arguments.model_dump(mode="json") if isinstance(arguments, BaseModel) else arguments
    if not isinstance(raw, Mapping):
        raise IdempotencyError("argumentos devem ser um mapeamento")
    data = _canonical(raw)
    for name in unordered:
        key = unicodedata.normalize("NFC", name)
        field = data.get(key)
        if isinstance(field, list):
            data[key] = sorted(field, key=_dumps)
    return _dumps(data)


def operation_id(
    action_id: str,
    target: str,
    arguments: Mapping[str, Any] | BaseModel,
    *,
    unordered: frozenset[str] = frozenset(),
) -> str:
    """Chave estável de uma operação: versão, tool da política, alvo e argumentos."""

    if not isinstance(action_id, str) or not _ACTION_ID.match(action_id):
        raise IdempotencyError(f"action_id inválido: {action_id!r}")
    if not isinstance(target, str) or not target.strip():
        raise IdempotencyError("alvo vazio")
    payload = "\0".join(
        (
            f"v{IDEMPOTENCY_VERSION}",
            action_id,
            unicodedata.normalize("NFC", target),
            normalize_arguments(arguments, unordered=unordered),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def requires_idempotency(rule: ActionRule | None) -> bool:
    """Só `risk: read` dispensa registro; tool sem entrada na política exige."""

    return rule is None or rule.risk != "read"


@dataclass(frozen=True)
class Outcome:
    """Único jeito de declarar o resultado de um efeito externo."""

    status: FinalStatus
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.status not in ("succeeded", "failed"):
            raise IdempotencyError(f"status final inválido: {self.status!r}")
        if self.status == "succeeded" and self.error_code is not None:
            raise IdempotencyError("sucesso não leva error_code")
        if self.error_code is not None and not _ERROR_CODE.match(self.error_code):
            raise IdempotencyError(f"error_code inválido: {self.error_code!r}")


@dataclass(frozen=True)
class OperationRecord:
    """Sem argumentos, alvo em claro, saída ou segredos."""

    operation_id: str
    action_id: str
    status: OperationStatus
    created_at: float
    updated_at: float
    error_code: str | None = None


class OperationExists(RuntimeError):
    """Já há registro que bloqueia a repetição; nada foi executado."""

    def __init__(self, record: OperationRecord) -> None:
        super().__init__(f"operação já registrada: {record.status}")
        self.record = record


class InMemoryOperationLedger:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.time,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        if window_seconds <= 0:
            raise IdempotencyError("janela deve ser positiva")
        self._clock = clock
        self._window = window_seconds
        self._records: dict[str, OperationRecord] = {}
        self._lock = threading.Lock()

    def lookup(self, op_id: str) -> OperationRecord | None:
        with self._lock:
            return self._records.get(op_id)

    def _blocks(self, record: OperationRecord, now: float) -> bool:
        if record.status in ("pending", "unknown"):
            return True
        return now - record.updated_at < self._window

    def begin(self, op_id: str, action_id: str) -> OperationRecord:
        if not _OPERATION_ID.match(op_id):
            raise IdempotencyError("operation_id inválido")
        if not _ACTION_ID.match(action_id):
            raise IdempotencyError(f"action_id inválido: {action_id!r}")
        with self._lock:
            now = self._clock()
            existing = self._records.get(op_id)
            if existing is not None and self._blocks(existing, now):
                raise OperationExists(existing)
            record = OperationRecord(op_id, action_id, "pending", now, now)
            self._records[op_id] = record
            return record

    def _transition(
        self,
        op_id: str,
        expected: OperationStatus,
        status: OperationStatus,
        error_code: str | None = None,
    ) -> OperationRecord:
        with self._lock:
            record = self._records.get(op_id)
            if record is None or record.status != expected:
                found = None if record is None else record.status
                raise IdempotencyError(f"transição proibida: {found} -> {status}")
            updated = replace(
                record, status=status, updated_at=self._clock(), error_code=error_code
            )
            self._records[op_id] = updated
            return updated

    def finish(self, op_id: str, outcome: Outcome) -> OperationRecord:
        if not isinstance(outcome, Outcome):
            raise IdempotencyError("resultado deve ser Outcome explícito")
        return self._transition(op_id, "pending", outcome.status, outcome.error_code)

    def mark_unknown(self, op_id: str) -> OperationRecord:
        return self._transition(op_id, "pending", "unknown")

    def recover(self) -> int:
        """Após reinício, todo `pending` vira `unknown` (nunca sucesso)."""

        with self._lock:
            pending = [r for r in self._records.values() if r.status == "pending"]
            now = self._clock()
            for record in pending:
                self._records[record.operation_id] = replace(
                    record, status="unknown", updated_at=now
                )
            return len(pending)

    def resolve_unknown(self, op_id: str, outcome: Outcome) -> OperationRecord:
        """Só decisão humana tira uma operação de `unknown`."""

        if not isinstance(outcome, Outcome):
            raise IdempotencyError("resultado deve ser Outcome explícito")
        return self._transition(op_id, "unknown", outcome.status, outcome.error_code)


def run_once(
    ledger: InMemoryOperationLedger,
    action_id: str,
    op_id: str,
    effect: Callable[[], object],
) -> OperationRecord:
    """Executa `effect` no máximo uma vez. Duplicata levanta `OperationExists`."""

    ledger.begin(op_id, action_id)
    try:
        result = effect()
    except Exception:
        return ledger.mark_unknown(op_id)
    except BaseException:
        ledger.mark_unknown(op_id)
        raise
    if isinstance(result, Outcome):
        return ledger.finish(op_id, result)
    return ledger.mark_unknown(op_id)
