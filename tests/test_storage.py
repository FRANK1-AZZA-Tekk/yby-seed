import sqlite3
from contextlib import closing
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.core.audit_contracts import AuditFinish, AuditStart
from src.core.storage import (
    StorageError,
    initialize_database,
    open_existing_database,
)


@pytest.fixture
def db_path(tmp_path):
    directory = tmp_path / "audit"
    directory.mkdir(mode=0o700)
    return directory / "audit.sqlite3"


def start_event(**changes):
    values = {
        "request_id": uuid4(),
        "started_at_ms": 1000,
        "model": "qwen3:4b",
    }
    values.update(changes)
    return AuditStart(**values)


def finish_event(request_id, **changes):
    values = {
        "request_id": request_id,
        "finished_at_ms": 1200,
        "elapsed_ms": 200,
        "status": "ok",
        "exit_code": 0,
    }
    values.update(changes)
    return AuditFinish(**values)


def test_initialization_uses_wal_and_version_one(db_path):
    initialize_database(db_path)
    with closing(sqlite3.connect(db_path)) as connection:
        assert connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0] == 1
        assert connection.execute(
            "PRAGMA journal_mode"
        ).fetchone()[0].lower() == "wal"


def test_open_missing_database_does_not_create_file(db_path):
    with pytest.raises(StorageError):
        open_existing_database(db_path)
    assert not db_path.exists()


def test_start_finish_and_reopen_preserve_record(db_path):
    initialize_database(db_path)
    store = open_existing_database(db_path)
    event = start_event()
    store.start(event)
    store.finish(finish_event(event.request_id))
    open_existing_database(db_path)

    with closing(sqlite3.connect(db_path)) as connection:
        row = connection.execute(
            "SELECT status, exit_code, elapsed_ms "
            "FROM audit_requests WHERE request_id = ?",
            (str(event.request_id),),
        ).fetchone()
    assert row == ("ok", 0, 200)


def test_initialization_does_not_replace_existing_file(db_path):
    db_path.write_bytes(b"CONTEUDO_EXISTENTE")
    with pytest.raises(StorageError):
        initialize_database(db_path)
    assert db_path.read_bytes() == b"CONTEUDO_EXISTENTE"


def test_duplicate_start_does_not_replace_record(db_path):
    initialize_database(db_path)
    store = open_existing_database(db_path)
    event = start_event()
    store.start(event)
    with pytest.raises(StorageError):
        store.start(event)


def test_finish_requires_existing_unfinished_record(db_path):
    initialize_database(db_path)
    store = open_existing_database(db_path)
    event = start_event()

    with pytest.raises(StorageError):
        store.finish(finish_event(event.request_id))

    store.start(event)
    store.finish(finish_event(event.request_id))

    with pytest.raises(StorageError):
        store.finish(finish_event(event.request_id))


def test_incompatible_version_is_not_overwritten(db_path):
    initialize_database(db_path)
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA user_version = 99")

    with pytest.raises(StorageError):
        open_existing_database(db_path)

    with closing(sqlite3.connect(db_path)) as connection:
        assert connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0] == 99


def test_unknown_schema_is_rejected(db_path):
    initialize_database(db_path)
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            connection.execute("CREATE TABLE unexpected (value TEXT)")

    with pytest.raises(StorageError):
        open_existing_database(db_path)


def test_model_is_bound_as_parameter(db_path):
    initialize_database(db_path)
    store = open_existing_database(db_path)
    model = "x'); DROP TABLE audit_requests; --"
    event = start_event(model=model)
    store.start(event)

    with closing(sqlite3.connect(db_path)) as connection:
        assert connection.execute(
            "SELECT model FROM audit_requests"
        ).fetchone()[0] == model


@pytest.mark.parametrize("field", ["prompt", "response", "metadata_json"])
def test_content_fields_are_rejected(field):
    with pytest.raises(ValidationError):
        start_event(**{field: "SEGREDO_TESTE"})


def test_status_and_exit_code_must_match():
    with pytest.raises(ValidationError):
        finish_event(uuid4(), status="ok", exit_code=7)


def test_locked_database_returns_controlled_error(db_path):
    initialize_database(db_path)
    store = open_existing_database(db_path)
    with closing(sqlite3.connect(db_path)) as blocker:
        blocker.execute("BEGIN IMMEDIATE")
        try:
            with pytest.raises(StorageError) as caught:
                store.start(start_event())
        finally:
            blocker.rollback()

    assert str(caught.value) == (
        "Não foi possível iniciar o registro de auditoria."
    )


def test_corrupt_database_has_controlled_error(db_path):
    initialize_database(db_path)
    db_path.write_bytes(b"SEGREDO_TESTE: arquivo invalido")

    with pytest.raises(StorageError) as caught:
        open_existing_database(db_path)

    assert "SEGREDO_TESTE" not in str(caught.value)


def test_failed_initialization_rolls_back_schema(db_path, monkeypatch):
    monkeypatch.setattr(
        "src.core.storage.INDEX_SQL",
        "CREATE INDEX",
    )

    with pytest.raises(StorageError):
        initialize_database(db_path)

    with closing(sqlite3.connect(db_path)) as connection:
        assert connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0] == 0

        objects = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%'"
        ).fetchall()

    assert objects == []
