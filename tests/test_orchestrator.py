from pathlib import Path

import pytest

from src.orchestrator import choose_model, classify_task
from src.tools.files import read_yby_file, safe_path, write_yby_file


def test_classify_firmware() -> None:
    assert classify_task("Faça build do firmware ESP32") == "firmware"


def test_classify_memory() -> None:
    assert classify_task("Busque no documento da memória") == "memory"


def test_choose_model_keeps_sensitive_local() -> None:
    choice = choose_model("research", sensitive=True)
    assert choice.provider == "ollama"
    assert choice.allow_cloud is False


def test_choose_model_research_may_use_cloud() -> None:
    choice = choose_model("research", privacy_level="P1")
    assert choice.provider == "openrouter"
    assert choice.allow_cloud is True


def test_safe_path_rejects_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.tools.files.ALLOWED_ROOT", tmp_path)
    with pytest.raises(ValueError):
        safe_path("../outside.txt")


def test_read_write_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.tools.files.ALLOWED_ROOT", tmp_path)
    assert write_yby_file("notes/a.txt", "olá") == "Arquivo salvo: notes/a.txt"
    assert read_yby_file("notes/a.txt") == "olá"
