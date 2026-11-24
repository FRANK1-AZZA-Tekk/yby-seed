"""Issue #121: CLI fecha engine/provider em sucesso e em erro (sem Ollama)."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from src.engine.hybrid import EngineReply
from src.main import cli
from src.voice.session import VoiceError, VoiceTurn


class _ClosableEngine:
    def __init__(self, reply: EngineReply) -> None:
        self.reply_value = reply
        self.close_calls = 0

    def reply(self, prompt: str, *, explicit_heavy: bool = False) -> EngineReply:
        return self.reply_value

    def close(self) -> None:
        self.close_calls += 1


class _BoomEngine(_ClosableEngine):
    def reply(self, prompt: str, *, explicit_heavy: bool = False) -> EngineReply:
        raise RuntimeError("falha no motor")


class _StubOllamaProvider:
    """Substituto de OllamaProvider que rastreia close()."""

    instances: list[_StubOllamaProvider] = []

    def __init__(self, base_url: str, timeout: float = 30, session: object | None = None) -> None:
        self.close_calls = 0
        self._finish = '{"action":"finish","answer":{"summary":"ok","validated":true}}'
        _StubOllamaProvider.instances.append(self)

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        return self._finish

    def close(self) -> None:
        self.close_calls += 1


@pytest.fixture(autouse=True)
def _reset_stub_provider() -> None:
    _StubOllamaProvider.instances.clear()


def test_ask_fecha_engine_no_sucesso(monkeypatch) -> None:
    engine = _ClosableEngine(
        EngineReply("ok", "local", "qwen2.5-coder:3b", ("ok",), None)
    )
    monkeypatch.setattr("src.main.build_engine", lambda: engine)
    result = CliRunner().invoke(cli, ["ask", "oi"])
    assert result.exit_code == 0
    assert engine.close_calls == 1


def test_ask_fecha_engine_quando_provider_none(monkeypatch) -> None:
    engine = _ClosableEngine(
        EngineReply(
            "",
            "none",
            "",
            ("local",),
            notice="sem nuvem",
        )
    )
    monkeypatch.setattr("src.main.build_engine", lambda: engine)
    result = CliRunner().invoke(cli, ["ask", "oi"])
    assert result.exit_code == 1
    assert engine.close_calls == 1


def test_ask_fecha_engine_quando_reply_falha(monkeypatch) -> None:
    engine = _BoomEngine(
        EngineReply("", "none", "", ("x",), None)
    )
    monkeypatch.setattr("src.main.build_engine", lambda: engine)
    with pytest.raises(RuntimeError, match="falha no motor"):
        CliRunner().invoke(cli, ["ask", "oi"], catch_exceptions=False)
    assert engine.close_calls == 1


def test_listen_fecha_engine_no_sucesso(monkeypatch) -> None:
    engine = _ClosableEngine(
        EngineReply("falado", "local", "qwen2.5-coder:3b", ("ok",), None)
    )
    monkeypatch.setattr("src.main.build_engine", lambda: engine)
    monkeypatch.setattr(
        "src.main.listen_once",
        lambda eng, *_a, **_k: VoiceTurn(
            transcript="oi",
            reply=eng.reply_value,
            tts_path=None,
            tts_notice=None,
        ),
    )
    result = CliRunner().invoke(cli, ["listen"])
    assert result.exit_code == 0
    assert engine.close_calls == 1


def test_ask_voice_fecha_engine_em_voice_error(monkeypatch) -> None:
    engine = _ClosableEngine(
        EngineReply("", "none", "", ("x",), None)
    )
    monkeypatch.setattr("src.main.build_engine", lambda: engine)
    monkeypatch.setattr(
        "src.main.listen_once",
        lambda *_a, **_k: (_ for _ in ()).throw(VoiceError("sem mic")),
    )
    result = CliRunner().invoke(cli, ["ask", "--voice"])
    assert result.exit_code == 1
    assert engine.close_calls == 1


def test_ask_voice_fecha_engine_no_sucesso(monkeypatch) -> None:
    engine = _ClosableEngine(
        EngineReply("voz", "local", "qwen2.5-coder:3b", ("ok",), None)
    )
    monkeypatch.setattr("src.main.build_engine", lambda: engine)
    monkeypatch.setattr(
        "src.main.listen_once",
        lambda eng, *_a, **_k: VoiceTurn(
            transcript="t",
            reply=eng.reply_value,
            tts_path=None,
            tts_notice=None,
        ),
    )
    result = CliRunner().invoke(cli, ["ask", "--voice"])
    assert result.exit_code == 0
    assert engine.close_calls == 1


def test_agent_local_fecha_provider_no_sucesso(monkeypatch) -> None:
    monkeypatch.setattr("src.main.OllamaProvider", _StubOllamaProvider)
    result = CliRunner().invoke(cli, ["agent", "tarefa", "--local"])
    assert result.exit_code == 0
    assert len(_StubOllamaProvider.instances) == 1
    assert _StubOllamaProvider.instances[0].close_calls == 1
    assert "status: completed" in result.output


def test_agent_local_fecha_provider_quando_loop_falha(monkeypatch) -> None:
    class _FailProvider(_StubOllamaProvider):
        def complete(self, prompt: str, *, model: str, system: str) -> str:
            raise RuntimeError("planner off")

    monkeypatch.setattr("src.main.OllamaProvider", _FailProvider)
    result = CliRunner().invoke(cli, ["agent", "tarefa", "--local"])
    assert result.exit_code == 1
    assert _FailProvider.instances[0].close_calls == 1


def test_agent_script_nao_instantia_ollama_provider(monkeypatch) -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = root / "examples" / "agent_demo_script.json"
    called = {"boom": False}

    def _boom(*_a, **_k) -> object:
        called["boom"] = True
        raise AssertionError("script não deve criar OllamaProvider")

    monkeypatch.setattr("src.main.OllamaProvider", _boom)
    result = CliRunner().invoke(cli, ["agent", "demo", "--script", str(script)])
    assert result.exit_code == 0
    assert called["boom"] is False