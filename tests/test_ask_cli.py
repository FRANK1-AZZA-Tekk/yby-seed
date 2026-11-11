"""CLI `ask` com o motor substituído. Não abre rede."""

from __future__ import annotations

from click.testing import CliRunner

import yby
from src.engine.hybrid import EngineReply
from src.main import build_engine, cli


class _ScriptedEngine:
    def __init__(self, reply: EngineReply) -> None:
        self.reply_value = reply
        self.calls: list[dict[str, object]] = []

    def reply(self, prompt: str, *, explicit_heavy: bool = False) -> EngineReply:
        self.calls.append({"prompt": prompt, "explicit_heavy": explicit_heavy})
        return self.reply_value


def test_yby_aponta_para_o_mesmo_cli() -> None:
    assert yby.cli is cli


def test_ask_imprime_a_resposta(monkeypatch) -> None:
    engine = _ScriptedEngine(
        EngineReply(
            text="uma lista guarda itens em ordem",
            provider="local",
            model="qwen2.5-coder:3b",
            reasons=("pedido dentro do limite local",),
            notice=None,
        )
    )
    monkeypatch.setattr("src.main.build_engine", lambda: engine)
    result = CliRunner().invoke(cli, ["ask", "explica", "uma", "lista"])

    assert result.exit_code == 0
    assert "uma lista guarda itens em ordem" in result.output
    assert engine.calls == [{"prompt": "explica uma lista", "explicit_heavy": False}]
    assert "qwen2.5-coder:3b" in result.output


def test_ask_heavy_repassa_a_flag(monkeypatch) -> None:
    engine = _ScriptedEngine(
        EngineReply(
            text="resposta longa",
            provider="cloud",
            model="grok-4.7",
            reasons=("flag --heavy",),
            notice=None,
        )
    )
    monkeypatch.setattr("src.main.build_engine", lambda: engine)
    result = CliRunner().invoke(cli, ["ask", "--heavy", "oi"])

    assert result.exit_code == 0
    assert engine.calls[0]["explicit_heavy"] is True
    assert "resposta longa" in result.output


def test_ask_sem_resposta_termina_com_erro(monkeypatch) -> None:
    engine = _ScriptedEngine(
        EngineReply(
            text="",
            provider="none",
            model="",
            reasons=("pedido dentro do limite local",),
            notice="YBY_CLOUD_API_KEY não está definida, então não há fallback de nuvem.",
        )
    )
    monkeypatch.setattr("src.main.build_engine", lambda: engine)
    result = CliRunner().invoke(cli, ["ask", "oi"])

    assert result.exit_code == 1
    assert "YBY_CLOUD_API_KEY" in result.output


def test_ask_vazio_nao_chama_o_motor(monkeypatch) -> None:
    called = {"sim": False}

    def _boom():
        called["sim"] = True
        raise AssertionError("não deveria montar o motor")

    monkeypatch.setattr("src.main.build_engine", _boom)
    result = CliRunner().invoke(cli, ["ask", "   "])

    assert result.exit_code != 0
    assert called["sim"] is False


def test_build_engine_e_substituivel() -> None:
    assert callable(build_engine)
