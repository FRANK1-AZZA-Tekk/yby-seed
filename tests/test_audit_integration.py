import sqlite3
from contextlib import closing
from unittest.mock import patch

import pytest
from click.testing import CliRunner

import src.core.audit as audit_module
import src.main as main
from src.core.storage import StorageError


@pytest.fixture(autouse=True)
def audit_db(tmp_path, monkeypatch):
    db = tmp_path / "audit.sqlite3"
    monkeypatch.setattr(audit_module, "AUDIT_DB_PATH", db)
    return db


def _successful_client():
    with patch("src.main.OllamaClient") as client_class:
        client = client_class.return_value
        client.is_healthy.return_value = True
        client.list_models.return_value = [main.DEFAULT_MODEL]
        client.generate.return_value = "ok"
        yield client_class


def test_ask_without_audit_does_not_create_db():
    with patch("src.main.OllamaClient") as client_class:
        client = client_class.return_value
        client.is_healthy.return_value = True
        client.list_models.return_value = [main.DEFAULT_MODEL]
        client.generate.return_value = "ok"

        result = CliRunner().invoke(main.cli, ["ask", "Olá"])

    assert result.exit_code == 0
    assert not audit_module.AUDIT_DB_PATH.exists()


def test_ask_with_audit_records_metadata_only():
    with patch("src.main.OllamaClient") as client_class:
        client = client_class.return_value
        client.is_healthy.return_value = True
        client.list_models.return_value = [main.DEFAULT_MODEL]
        client.generate.return_value = "resposta"

        result = CliRunner().invoke(main.cli, ["ask", "--audit", "Olá"])

    assert result.exit_code == 0
    assert audit_module.AUDIT_DB_PATH.exists()

    with closing(sqlite3.connect(audit_module.AUDIT_DB_PATH)) as connection:
        row = connection.execute(
            "SELECT status, exit_code, model FROM audit_requests"
        ).fetchone()

    assert row == ("ok", 0, main.DEFAULT_MODEL)


def test_ask_audit_private_records_nothing():
    with patch("src.main.OllamaClient") as client_class:
        client = client_class.return_value
        client.is_healthy.return_value = True
        client.list_models.return_value = [main.DEFAULT_MODEL]
        client.generate.return_value = "ok"

        result = CliRunner().invoke(
            main.cli,
            ["ask", "--audit", "--private", "Olá"],
        )

    assert result.exit_code == 0
    assert not audit_module.AUDIT_DB_PATH.exists()


def test_audit_failure_does_not_break_ask():
    with patch(
        "src.core.audit.open_existing_database",
        side_effect=StorageError(
            "Não foi possível iniciar o registro de auditoria."
        ),
    ), patch(
        "src.core.audit.initialize_database",
        side_effect=StorageError(
            "Não foi possível iniciar o registro de auditoria."
        ),
    ), patch(
        "src.main.OllamaClient"
    ) as client_class:
        client = client_class.return_value
        client.is_healthy.return_value = True
        client.list_models.return_value = [main.DEFAULT_MODEL]
        client.generate.return_value = "ok"

        result = CliRunner().invoke(main.cli, ["ask", "--audit", "Olá"])

    assert result.exit_code == 0
    assert result.output.strip() == "ok"


def test_empty_response_records_empty_status():
    with patch("src.main.OllamaClient") as client_class:
        client = client_class.return_value
        client.is_healthy.return_value = True
        client.list_models.return_value = [main.DEFAULT_MODEL]
        client.generate.return_value = ""

        result = CliRunner().invoke(main.cli, ["ask", "--audit", "Olá"])

    assert result.exit_code == 4

    with closing(sqlite3.connect(audit_module.AUDIT_DB_PATH)) as connection:
        row = connection.execute(
            "SELECT status, exit_code FROM audit_requests"
        ).fetchone()

    assert row == ("empty", 4)


def test_policy_error_records_error_status():
    from src.core.ollama_client import OllamaPolicyError

    with patch("src.main.OllamaClient") as client_class:
        client = client_class.return_value
        client.is_healthy.side_effect = OllamaPolicyError(
            "Endpoint do Ollama não permitido pela política local."
        )

        result = CliRunner().invoke(main.cli, ["ask", "--audit", "Olá"])

    assert result.exit_code == 6

    with closing(sqlite3.connect(audit_module.AUDIT_DB_PATH)) as connection:
        row = connection.execute(
            "SELECT status, exit_code FROM audit_requests"
        ).fetchone()

    assert row == ("error", 6)
