"""SQLite de auditoria, sem conteúdo de conversa e sem efeitos no import."""

import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

from .audit_contracts import AuditFinish, AuditStart


SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 2000

TABLE_SQL = """
CREATE TABLE audit_requests (
    request_id TEXT PRIMARY KEY NOT NULL,
    started_at_ms INTEGER NOT NULL CHECK (started_at_ms >= 0),
    finished_at_ms INTEGER,
    elapsed_ms INTEGER CHECK (elapsed_ms >= 0),
    backend TEXT NOT NULL CHECK (backend = 'ollama'),
    model TEXT NOT NULL CHECK (length(model) BETWEEN 1 AND 128),
    status TEXT NOT NULL CHECK (
        status IN (
            'started', 'ok', 'unavailable', 'model_missing',
            'empty', 'client_error', 'interrupted'
        )
    ),
    exit_code INTEGER,
    CHECK (
        (
            status = 'started'
            AND finished_at_ms IS NULL
            AND elapsed_ms IS NULL
            AND exit_code IS NULL
        )
        OR
        (
            status <> 'started'
            AND finished_at_ms IS NOT NULL
            AND finished_at_ms >= 0
            AND elapsed_ms IS NOT NULL
            AND exit_code IS NOT NULL
            AND exit_code = CASE status
                WHEN 'ok' THEN 0
                WHEN 'unavailable' THEN 2
                WHEN 'model_missing' THEN 3
                WHEN 'empty' THEN 4
                WHEN 'client_error' THEN 7
                WHEN 'interrupted' THEN 130
            END
        )
    )
)
""".strip()

INDEX_SQL = """
CREATE INDEX idx_audit_started_at
ON audit_requests(started_at_ms)
""".strip()


class StorageError(RuntimeError):
    """Falha com mensagem pública controlada."""


def _check_directory(path: Path) -> None:
    parent = path.parent
    if not parent.is_dir():
        raise StorageError("Diretório de auditoria inexistente.")
    if os.name == "posix":
        info = parent.stat()
        if info.st_uid != os.getuid():
            raise StorageError("Diretório de auditoria pertence a outro usuário.")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise StorageError("Diretório de auditoria deve ser privado.")


def _check_existing_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise StorageError("Banco de auditoria ausente ou inválido.")
    if os.name == "posix":
        info = path.stat()
        if info.st_uid != os.getuid():
            raise StorageError("Banco de auditoria pertence a outro usuário.")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise StorageError("Banco de auditoria deve ser privado.")


def _validate_schema(connection: sqlite3.Connection) -> None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        raise StorageError("Versão de auditoria incompatível.")

    actual = {
        name: sql.strip().rstrip(";")
        for name, sql in connection.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%'"
        )
    }
    expected = {
        "audit_requests": TABLE_SQL,
        "idx_audit_started_at": INDEX_SQL,
    }
    if actual != expected:
        raise StorageError("Schema de auditoria incompatível.")

    journal_mode = connection.execute(
        "PRAGMA journal_mode"
    ).fetchone()[0]
    if journal_mode.lower() != "wal":
        raise StorageError("Banco de auditoria não está em modo WAL.")


def _connect_existing(path: Path) -> sqlite3.Connection:
    _check_directory(path)
    _check_existing_file(path)
    uri = path.as_uri() + "?mode=rw"
    connection = sqlite3.connect(
        uri,
        uri=True,
        timeout=BUSY_TIMEOUT_MS / 1000,
    )
    try:
        _validate_schema(connection)
        connection.execute("PRAGMA synchronous = FULL")
        return connection
    except BaseException:
        connection.close()
        raise


def initialize_database(path: Path) -> None:
    """Cria banco novo; nunca substitui arquivo existente."""
    path = Path(path).absolute()
    try:
        _check_directory(path)
        descriptor = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
        os.close(descriptor)

        with closing(sqlite3.connect(
            path,
            timeout=BUSY_TIMEOUT_MS / 1000,
        )) as connection:
            mode = connection.execute(
                "PRAGMA journal_mode = WAL"
            ).fetchone()[0]
            if mode.lower() != "wal":
                raise StorageError("Não foi possível ativar WAL.")
            connection.execute("PRAGMA synchronous = FULL")
            with connection:
                connection.execute(TABLE_SQL)
                connection.execute(INDEX_SQL)
                connection.execute("PRAGMA user_version = 1")
            _validate_schema(connection)
    except StorageError:
        raise
    except (sqlite3.Error, OSError, ValueError):
        raise StorageError(
            "Não foi possível inicializar a auditoria."
        ) from None


class SQLiteAuditStore:
    """Operações curtas; nenhuma conexão fica aberta entre chamadas."""

    def __init__(self, path: Path):
        self.path = Path(path).absolute()

    def start(self, event: AuditStart) -> None:
        try:
            with closing(_connect_existing(self.path)) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO audit_requests (
                            request_id, started_at_ms,
                            backend, model, status
                        ) VALUES (?, ?, ?, ?, 'started')
                        """,
                        (
                            str(event.request_id),
                            event.started_at_ms,
                            event.backend,
                            event.model,
                        ),
                    )
        except StorageError:
            raise
        except (sqlite3.Error, OSError, ValueError, OverflowError):
            raise StorageError(
                "Não foi possível iniciar o registro de auditoria."
            ) from None

    def finish(self, event: AuditFinish) -> None:
        try:
            with closing(_connect_existing(self.path)) as connection:
                with connection:
                    cursor = connection.execute(
                        """
                        UPDATE audit_requests
                        SET finished_at_ms = ?, elapsed_ms = ?,
                            status = ?, exit_code = ?
                        WHERE request_id = ? AND status = 'started'
                        """,
                        (
                            event.finished_at_ms,
                            event.elapsed_ms,
                            event.status,
                            event.exit_code,
                            str(event.request_id),
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise StorageError(
                            "Registro ausente ou já concluído."
                        )
        except StorageError:
            raise
        except (sqlite3.Error, OSError, ValueError, OverflowError):
            raise StorageError(
                "Não foi possível concluir o registro de auditoria."
            ) from None


def open_existing_database(path: Path) -> SQLiteAuditStore:
    path = Path(path).absolute()
    try:
        with closing(_connect_existing(path)):
            pass
    except StorageError:
        raise
    except (sqlite3.Error, OSError, ValueError):
        raise StorageError(
            "Não foi possível abrir a auditoria."
        ) from None
    return SQLiteAuditStore(path)
