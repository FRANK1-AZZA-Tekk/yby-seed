"""Lote 13: envelope PT-BR (ask --explain / gate / run refuse). Sem rede."""

from __future__ import annotations

from click.testing import CliRunner

from src.conversation.explain import (
    format_cli_error,
    format_command_decision,
    format_engine_reply,
    format_vague_ask,
    is_vague_request,
)
from src.engine.hybrid import EngineReply
from src.main import cli
from src.safety.policy import Decision


def test_is_vague_for_short_greetings() -> None:
    assert is_vague_request("oi")
    assert is_vague_request("ajuda")
    assert not is_vague_request("explica como funciona uma lista em Python")


def test_format_vague_ask_tem_blocos_e_perguntas() -> None:
    text = format_vague_ask("oi")
    for label in ("Entendi:", "Falta:", "Proposta:", "Risco:", "Próximo passo:", "Como reverter:"):
        assert label in text
    assert "Perguntas:" in text
    assert text.count("\n  ") >= 3


def test_format_engine_reply_redige_segredo() -> None:
    secret = "sk-or-v1-" + ("a" * 24)
    out = format_engine_reply(
        prompt=f"use a chave {secret}",
        text=f"ok com {secret}",
        provider="local",
        model="qwen",
        reasons=("teste",),
        notice=None,
    )
    assert secret not in out
    assert "API_KEY_REDACTED" in out
    assert "Entendi:" in out


def test_format_command_decision_refuse() -> None:
    decision = Decision("refuse", "padrão destrutivo: rm -rf /")
    out = format_command_decision("rm -rf /", decision)
    assert out.startswith("refuse:")
    assert "Entendi:" in out
    assert "nada foi executado" in out.casefold() or "Como reverter:" in out


def test_format_cli_error_envelope() -> None:
    out = format_cli_error(
        kind="vault",
        detail="YBY_VAULT_PATH não definida",
        next_step="configure o vault",
    )
    assert "Entendi: falha: vault" in out
    assert "YBY_VAULT_PATH" in out


def test_ask_explain_vague_nao_chama_motor(monkeypatch) -> None:
    called = {"sim": False}

    def _boom():
        called["sim"] = True
        raise AssertionError("não deveria montar o motor")

    monkeypatch.setattr("src.main.build_engine", _boom)
    result = CliRunner().invoke(cli, ["ask", "--explain", "oi"])

    assert result.exit_code == 0
    assert called["sim"] is False
    assert "Entendi:" in result.output
    assert "Perguntas:" in result.output


def test_ask_explain_imprime_envelope(monkeypatch) -> None:
    class _Engine:
        def reply(self, prompt: str, *, explicit_heavy: bool = False) -> EngineReply:
            return EngineReply(
                text="resposta clara",
                provider="local",
                model="qwen2.5-coder:3b",
                reasons=("pedido dentro do limite local",),
                notice=None,
            )

    monkeypatch.setattr("src.main.build_engine", lambda: _Engine())
    result = CliRunner().invoke(
        cli,
        ["ask", "--explain", "explica", "uma", "lista", "em", "python"],
    )

    assert result.exit_code == 0
    assert "Entendi:" in result.output
    assert "Proposta: resposta clara" in result.output
    assert "resposta clara" in result.output


def test_ask_sem_explain_continua_cru(monkeypatch) -> None:
    class _Engine:
        def reply(self, prompt: str, *, explicit_heavy: bool = False) -> EngineReply:
            return EngineReply(
                text="texto cru",
                provider="local",
                model="qwen",
                reasons=("ok",),
                notice=None,
            )

    monkeypatch.setattr("src.main.build_engine", lambda: _Engine())
    result = CliRunner().invoke(cli, ["ask", "explica", "lista"])

    assert result.exit_code == 0
    assert "texto cru" in result.output
    assert "Entendi:" not in result.output


def test_gate_imprime_envelope() -> None:
    result = CliRunner().invoke(cli, ["gate", "ls"])
    assert result.exit_code == 0
    assert "Entendi:" in result.output
    assert result.output.startswith("run:") or "run:" in result.output.splitlines()[0]


def test_run_refuse_imprime_envelope(monkeypatch) -> None:
    from src.actions.runner import RunResult

    monkeypatch.setattr(
        "src.main.run_command",
        lambda command, **kwargs: RunResult(
            decision=Decision("refuse", "padrão destrutivo: rm -rf /"),
            approved=False,
            executed=False,
            exit_code=None,
            stdout="",
            stderr="",
        ),
    )
    result = CliRunner().invoke(cli, ["run", "rm", "-rf", "/"])
    assert result.exit_code == 1
    assert "Entendi:" in result.output
    assert "refuse" in result.output
