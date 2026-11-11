"""Testes do framework da Camada A (sem LLM / Ollama)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from src.app import App, Layer, LayerStatus, create_app, load_settings


def test_load_settings_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("YBY_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("YBY_SKILLS_MODE", raising=False)
    monkeypatch.delenv("YBY_MEMORY_BACKEND", raising=False)
    settings = load_settings(tmp_path)
    assert settings.project_root == tmp_path
    assert settings.data_dir == tmp_path / ".yby"
    assert settings.llm_provider_preference == "auto"
    assert settings.skills_mode == "dry_run"
    assert settings.memory_backend == "none"
    assert settings.has_openrouter_key is False
    assert settings.ux_locale == "pt"


def test_layer_registry_form_and_briefing_ready() -> None:
    app = create_app()
    assert app.layers.get(Layer.FORM).status == LayerStatus.READY
    assert app.layers.get(Layer.BRIEFING).status == LayerStatus.READY
    assert app.layers.get(Layer.SKILLS).status == LayerStatus.PLANNED
    assert app.layers.get(Layer.MEMORY).status == LayerStatus.PLANNED
    table = app.layers.format_table()
    assert "Forma do produto" in table
    assert "Briefing" in table


def test_dispatch_help_and_status() -> None:
    out = io.StringIO()
    err = io.StringIO()
    app = App(settings=load_settings(), stdout=out, stderr=err)
    assert app.dispatch(["help"]) == 0
    assert "/brief" in out.getvalue()
    out.seek(0)
    out.truncate(0)
    assert app.dispatch(["status"]) == 0
    assert "Skills mode: dry_run" in out.getvalue()
    assert app.dispatch(["layers"]) == 0


def test_dispatch_unknown_command() -> None:
    err = io.StringIO()
    app = App(settings=load_settings(), stdout=io.StringIO(), stderr=err)
    assert app.dispatch(["nope"]) == 2
    assert "desconhecido" in err.getvalue()


def test_handle_line_quit_and_slash() -> None:
    out = io.StringIO()
    app = App(settings=load_settings(), stdout=out, stderr=io.StringIO())
    assert app.handle_line("quit") == 0
    assert app.handle_line("/status") is None
    assert "YBY SEED" in out.getvalue()


def test_handle_line_chat_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    out = io.StringIO()
    app = App(settings=load_settings(), stdout=out, stderr=io.StringIO())

    monkeypatch.setattr(
        "modules.llm_brain.load_llm_config",
        lambda: type("C", (), {"provider": "mock", "model": "m"})(),
    )
    monkeypatch.setattr(
        "modules.llm_brain.ask_llm", lambda text, config=None: f"eco:{text}"
    )

    assert app.handle_line("olá hub") is None
    assert "eco:olá hub" in out.getvalue()


def test_yby_seed_facade_importable() -> None:
    from yby_seed import main

    assert callable(main)
