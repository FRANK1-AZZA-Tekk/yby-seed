"""Contrato CLI do comando `yby agent` (offline; sem Ollama/rede)."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.engine.providers import ProviderError
from src.main import cli

ROOT = Path(__file__).resolve().parents[1]
DEMO_SCRIPT = ROOT / "examples" / "agent_demo_script.json"


def test_agent_script_happy_path() -> None:
    result = CliRunner().invoke(
        cli,
        ["agent", "demo", "--script", str(DEMO_SCRIPT)],
    )
    assert result.exit_code == 0
    assert "status: completed" in result.output
    assert "Entregável mínimo validado" in result.output


def test_agent_script_json_flag() -> None:
    result = CliRunner().invoke(
        cli,
        ["agent", "demo", "--script", str(DEMO_SCRIPT), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "completed"
    assert payload["final_answer"]["summary"] == "Entregável mínimo validado"
    assert payload["iterations"] >= 1


def test_agent_sem_modo() -> None:
    result = CliRunner().invoke(cli, ["agent", "sem-modo"])
    assert result.exit_code == 1
    assert "--script" in result.output
    assert "--local" in result.output


def test_agent_script_e_local_juntos() -> None:
    result = CliRunner().invoke(
        cli,
        ["agent", "conflito", "--script", str(DEMO_SCRIPT), "--local"],
    )
    assert result.exit_code == 1
    assert "Use apenas um de --script ou --local." in result.output


def test_agent_script_json_nao_array(tmp_path: Path) -> None:
    bad = tmp_path / "not-array.json"
    bad.write_text("{}\n", encoding="utf-8")
    result = CliRunner().invoke(
        cli,
        ["agent", "json-ruim", "--script", str(bad)],
    )
    assert result.exit_code == 1
    assert "O script deve ser um JSON array de passos." in result.output


class _Cfg:
    ollama_base_url = "http://127.0.0.1:11434"
    local_model = "qwen2.5-coder:3b"
    ollama_timeout = 1.0


class _FakeOllama:
    last: _FakeOllama | None = None

    def __init__(self, _base_url: str, *, timeout: float, session=None) -> None:
        self.closed = False
        self.close_calls = 0
        _FakeOllama.last = self

    def close(self) -> None:
        self.close_calls += 1
        self.closed = True

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        return '{"action":"abort","reason":"fim teste"}'


def test_agent_script_nao_instancia_ollama(monkeypatch) -> None:
    def _boom(*_a, **_k):
        msg = "OllamaProvider não deve ser usado com --script"
        raise AssertionError(msg)

    monkeypatch.setattr("src.main.OllamaProvider", _boom)
    result = CliRunner().invoke(
        cli,
        ["agent", "demo", "--script", str(DEMO_SCRIPT)],
    )
    assert result.exit_code == 0
    assert "status: completed" in result.output


def test_agent_local_fecha_ollama_no_fim(monkeypatch) -> None:
    monkeypatch.setattr("src.main.OllamaProvider", _FakeOllama)
    monkeypatch.setattr("src.main.EngineConfig.from_env", lambda: _Cfg())
    result = CliRunner().invoke(cli, ["agent", "tarefa offline", "--local"])

    assert result.exit_code == 2
    assert _FakeOllama.last is not None
    assert _FakeOllama.last.close_calls == 1
    assert _FakeOllama.last.closed is True
    assert "status: aborted" in result.output


def test_agent_local_falha_config_nao_chama_close(monkeypatch) -> None:
    class _NeverOllama(_FakeOllama):
        def close(self) -> None:
            raise AssertionError("close não deve rodar se a config falhar")

    monkeypatch.setattr("src.main.OllamaProvider", _NeverOllama)

    def _boom():
        raise OSError("sem config")

    monkeypatch.setattr("src.main.EngineConfig.from_env", _boom)
    result = CliRunner().invoke(cli, ["agent", "x", "--local"])

    assert result.exit_code != 0
    assert isinstance(result.exception, OSError)


def test_agent_local_fecha_apos_falha_do_planner(monkeypatch) -> None:
    class _FailingOllama(_FakeOllama):
        def complete(self, prompt: str, *, model: str, system: str) -> str:
            raise ProviderError("ollama indisponível")

    monkeypatch.setattr("src.main.OllamaProvider", _FailingOllama)
    monkeypatch.setattr("src.main.EngineConfig.from_env", lambda: _Cfg())
    result = CliRunner().invoke(cli, ["agent", "tarefa", "--local"])

    assert result.exit_code == 1
    assert _FailingOllama.last is not None
    assert _FailingOllama.last.close_calls == 1
    assert "status: error" in result.output


def test_agent_local_close_falha_preserva_systemexit_de_erro(monkeypatch) -> None:
    class _BrokenClose(_FakeOllama):
        def complete(self, prompt: str, *, model: str, system: str) -> str:
            return "isto não é json"

        def close(self) -> None:
            self.close_calls += 1
            raise RuntimeError("falha no cleanup")

    monkeypatch.setattr("src.main.OllamaProvider", _BrokenClose)
    monkeypatch.setattr("src.main.EngineConfig.from_env", lambda: _Cfg())
    result = CliRunner().invoke(cli, ["agent", "tarefa", "--local"])

    assert result.exit_code == 1
    assert _BrokenClose.last is not None
    assert _BrokenClose.last.close_calls == 1
