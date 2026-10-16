"""
Auditoria opt-in de metadados para o comando ask.

Principios:
- Nada e persistido por padrao; apenas --audit habilita.
- --private sempre prevalece: interacao privada nao grava nada.
- Somente metadados sao gravados (nunca prompt, resposta ou conteudo).
- Falha de auditoria e best-effort: nunca impede a resposta ao usuario.
"""

import os
import time
from contextlib import contextmanager
from uuid import uuid4

from loguru import logger

from src.core.audit_contracts import AuditFinish, AuditStart
from src.core.storage import (
    StorageError,
    initialize_database,
    open_existing_database,
)

AUDIT_DB_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "data",
        "audit",
        "audit.sqlite3",
    )
)


class AuditRecorder:
    """Registra o fim de uma interacao auditada (best-effort)."""

    def __init__(self, store, request_id, started_at_ms):
        self._store = store
        self._request_id = request_id
        self._started_at_ms = started_at_ms
        self._finished = False

    def finish(self, status: str, exit_code: int) -> None:
        if self._finished:
            return
        self._finished = True
        finished_at_ms = time.time_ns() // 1_000_000
        try:
            self._store.finish(
                AuditFinish(
                    request_id=self._request_id,
                    finished_at_ms=finished_at_ms,
                    elapsed_ms=finished_at_ms - self._started_at_ms,
                    status=status,
                    exit_code=exit_code,
                )
            )
        except StorageError:
            logger.warning("Não foi possível concluir a auditoria.")


@contextmanager
def audit_context(model: str):
    """Contexto de auditoria; rende AuditRecorder ou None.

    Se o chamador não concluir explicitamente, o registro é fechado
    como erro para não deixar linhas incompletas no banco.
    """
    request_id = uuid4()
    started_at_ms = time.time_ns() // 1_000_000
    try:
        try:
            store = open_existing_database(AUDIT_DB_PATH)
        except StorageError:
            initialize_database(AUDIT_DB_PATH)
            store = open_existing_database(AUDIT_DB_PATH)
        store.start(
            AuditStart(
                request_id=request_id,
                started_at_ms=started_at_ms,
                model=model,
            )
        )
    except StorageError:
        logger.warning("Não foi possível iniciar a auditoria.")
        yield None
        return

    recorder = AuditRecorder(store, request_id, started_at_ms)
    try:
        yield recorder
    finally:
        recorder.finish("error", 1)
