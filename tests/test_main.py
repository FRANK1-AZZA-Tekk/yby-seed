"""Testes da Camada 1 do YBY SEED.

Estes testes não dependem de Ollama real, Docker, rede externa
ou serviços pagos.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from click.testing import CliRunner

import src.main as main


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_check_python_accepts_supported_version() -> None:
    main.check_python()


def test_check_python_rejects_old_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main.sys, "version_info", (3, 10, 0))

    with pytest.raises(RuntimeError, match="Python 3.11"):
        main.check_python()


def test_check_dependencies_returns_required_modules() -> None:
    found = main.check_dependencies()

    assert "click" in found
    assert "httpx" in found
    assert "loguru" in found
    assert "pydantic" in found


def test_check_dependencies_detects_missing_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_find_spec(name: str):
        if name == "httpx":
            return None
        return importlib.util.find_spec(name)

    monkeypatch.setattr(main.importlib.util, "find_spec", fake_find_spec)

    with pytest.raises(RuntimeError, match="httpx"):
        main.check_dependencies()


def test_check_project_structure_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "requirements.txt").write_text("click\n", encoding="utf-8")

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "REQUIRED_PATHS",
        (
            tmp_path / "src",
            tmp_path / "tests",
            tmp_path / "requirements.txt",
        ),
    )

    main.check_project_structure()


def test_check_project_structure_detects_missing_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "REQUIRED_PATHS",
        (tmp_path / "requirements.txt",),
    )

    with pytest.raises(RuntimeError, match="Estrutura do projeto incompleta"):
        main.check_project_structure()


def test_check_ollama_returns_models() -> None:
    payload = {"models": [{"name": "llama3.2:3b"}]}

    def fake_get(url: str, timeout: float):
        assert url == "http://localhost:11434/api/tags"
        return httpx.Response(
            200,
            json=payload,
            request=httpx.Request("GET", url),
        )

    with patch.object(main.httpx, "get", side_effect=fake_get):
        result = main.check_ollama()

    assert result["available"] is True
    assert result["models"][0]["name"] == "llama3.2:3b"


def test_check_ollama_fails_when_unavailable() -> None:
    def fake_get(url: str, timeout: float):
        raise httpx.ConnectError("connection refused")

    with patch.object(main.httpx, "get", side_effect=fake_get):
        with pytest.raises(RuntimeError, match="Ollama não está acessível"):
            main.check_ollama()


def test_check_ollama_fails_with_invalid_payload() -> None:
    def fake_get(url: str, timeout: float):
        return httpx.Response(
            200,
            text="not-json",
            request=httpx.Request("GET", url),
        )

    with patch.object(main.httpx, "get", side_effect=fake_get):
        with pytest.raises(RuntimeError, match="payload inválido"):
            main.check_ollama()


def test_resolve_pytest_prefers_venv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    pytest_path = venv_bin / "pytest"
    pytest_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(main, "VENV_BIN", venv_bin)

    assert main.resolve_pytest() == pytest_path


def test_resolve_pytest_fails_when_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "VENV_BIN", tmp_path / ".venv" / "bin")
    monkeypatch.setattr(main.shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError, match="pytest não encontrado"):
        main.resolve_pytest()


def test_doctor_fails_when_ollama_is_unavailable(runner: CliRunner) -> None:
    def fake_check_ollama(timeout: float = 2.0):
        raise RuntimeError("Ollama não está acessível")

    with patch.object(main, "check_ollama", side_effect=fake_check_ollama):
        result = runner.invoke(main.cli, ["doctor"])

    assert result.exit_code == 1


def test_setup_fails_when_ollama_is_unavailable(runner: CliRunner) -> None:
    def fake_check_ollama(timeout: float = 2.0):
        raise RuntimeError("Ollama não está acessível")

    with patch.object(main, "check_ollama", side_effect=fake_check_ollama):
        result = runner.invoke(main.cli, ["setup"])

    assert result.exit_code == 1


def test_run_fails_when_ollama_is_unavailable(runner: CliRunner) -> None:
    def fake_check_ollama(timeout: float = 2.0):
        raise RuntimeError("Ollama não está acessível")

    with patch.object(main, "check_ollama", side_effect=fake_check_ollama):
        result = runner.invoke(main.cli, ["run"])

    assert result.exit_code == 1


def test_test_command_propagates_pytest_failure(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_pytest = tmp_path / "pytest"
    fake_pytest.write_text("", encoding="utf-8")

    monkeypatch.setattr(main, "resolve_pytest", lambda: fake_pytest)

    def fake_run(*args, **kwargs):
        class Result:
            returncode = 2

        return Result()

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    result = runner.invoke(main.cli, ["test"])

    assert result.exit_code == 2


def test_cli_help_works(runner: CliRunner) -> None:
    result = runner.invoke(main.cli, ["--help"])

    assert result.exit_code == 0
    assert "YBY SEED" in result.output
