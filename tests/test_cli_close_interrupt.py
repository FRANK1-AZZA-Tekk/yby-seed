"""`close()` do engine/provider também roda em Ctrl+C (#121). Não abre rede."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from src.main import cli


class _InterruptedEngine:
    def __init__(self) -> None:
        self.close_calls = 0

    def reply(self, prompt: str, *, explicit_heavy: bool = False):
        raise KeyboardInterrupt

    def close(self) -> None:
        self.close_calls += 1


class _Cfg:
    ollama_base_url = "http://127.0.0.1:11434"
    local_model = "qwen2.5-coder:3b"
    ollama_timeout = 1.0


class _InterruptedOllama:
    last: _InterruptedOllama | None = None

    def __init__(self, _base_url: str, *, timeout: float, session=None) -> None:
        self.close_calls = 0
        _InterruptedOllama.last = self

    def close(self) -> None:
        self.close_calls += 1

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        raise KeyboardInterrupt


def test_ask_fecha_engine_em_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _InterruptedEngine()
    monkeypatch.setattr("src.main.build_engine", lambda: engine)

    result = CliRunner().invoke(cli, ["ask", "oi"])

    assert result.exit_code != 0
    assert engine.close_calls == 1


def test_listen_fecha_engine_em_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _InterruptedEngine()
    monkeypatch.setattr("src.main.build_engine", lambda: engine)

    def _interrupted(*_a, **_k):
        raise KeyboardInterrupt

    monkeypatch.setattr("src.main.listen_once", _interrupted)
    monkeypatch.setattr("src.main.voice_config_from_env", lambda: object())

    result = CliRunner().invoke(cli, ["listen"])

    assert result.exit_code != 0
    assert engine.close_calls == 1


def test_agent_local_fecha_provider_em_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.main.OllamaProvider", _InterruptedOllama)
    monkeypatch.setattr("src.main.EngineConfig.from_env", lambda: _Cfg())

    result = CliRunner().invoke(cli, ["agent", "tarefa", "--local"])

    assert result.exit_code != 0
    assert _InterruptedOllama.last is not None
    assert _InterruptedOllama.last.close_calls == 1
