"""CLI `route`: previsão de roteamento sem motor nem rede."""

from __future__ import annotations

from click.testing import CliRunner

from src.engine.config import EngineConfig
from src.engine.hybrid import EngineReply, route_decision_from_config
from src.engine.routing import route_display_reasons
from src.main import cli


def test_route_pedido_curto_local() -> None:
    result = CliRunner().invoke(cli, ["route", "explica", "uma", "lista"])

    assert result.exit_code == 0
    assert "previsão:" in result.output
    assert "rota: local" in result.output
    assert "pedido dentro do limite local" in result.output


def test_route_heavy_vai_para_nuvem() -> None:
    result = CliRunner().invoke(cli, ["route", "--heavy", "oi"])

    assert result.exit_code == 0
    assert "rota: cloud" in result.output
    assert "flag --heavy" in result.output


def test_route_limiar_configuravel_por_env() -> None:
    result = CliRunner().invoke(
        cli,
        ["route", "abcd"],
        env={"YBY_HEAVY_MIN_CHARS": "4"},
    )

    assert result.exit_code == 0
    assert "rota: cloud" in result.output
    assert "caracteres" in result.output


def test_route_paridade_com_route_decision_from_config() -> None:
    prompt = "Pensa mais sobre recursão"
    config = EngineConfig.from_env(
        {
            "YBY_HEAVY_MIN_CHARS": "1200",
            "YBY_HEAVY_MIN_LINES": "25",
            "YBY_HEAVY_MIN_QUESTIONS": "3",
        }
    )
    expected = route_decision_from_config(config, prompt, explicit_heavy=False)

    result = CliRunner().invoke(
        cli,
        ["route", prompt],
        env={
            "YBY_HEAVY_MIN_CHARS": "1200",
            "YBY_HEAVY_MIN_LINES": "25",
            "YBY_HEAVY_MIN_QUESTIONS": "3",
        },
    )

    assert result.exit_code == 0
    assert f"rota: {expected.target}" in result.output
    for reason in route_display_reasons(expected):
        assert reason in result.output
    assert "frase explícita: pensa mais" not in result.output


def test_route_paridade_com_ask_na_decisao(monkeypatch) -> None:
    captured: list[tuple[str, bool]] = []

    class _Engine:
        def reply(self, prompt: str, *, explicit_heavy: bool = False) -> EngineReply:
            config = EngineConfig.from_env()
            decision = route_decision_from_config(config, prompt, explicit_heavy=explicit_heavy)
            captured.append((decision.target, decision.reasons))
            return EngineReply(
                text="ok",
                provider=decision.target,
                model="test",
                reasons=decision.reasons,
                notice=None,
            )

        def close(self) -> None:
            return None

    monkeypatch.setattr("src.main.build_engine", lambda: _Engine())

    pedido = "explica uma lista"
    route_result = CliRunner().invoke(cli, ["route", pedido])
    ask_result = CliRunner().invoke(cli, ["ask", pedido])

    assert route_result.exit_code == 0
    assert ask_result.exit_code == 0
    assert captured
    target, reasons = captured[-1]
    assert f"rota: {target}" in route_result.output
    motivos_ask = "; ".join(reasons)
    assert motivos_ask in ask_result.output
    assert "pedido dentro do limite local" in route_result.output


def test_route_nao_instancia_motor_nem_provedores(monkeypatch) -> None:
    def _fail(*_args, **_kwargs):
        msg = "não deve instanciar motor ou provedor"
        raise AssertionError(msg)

    monkeypatch.setattr("src.main.build_engine", _fail)
    monkeypatch.setattr("src.engine.hybrid.engine_from_env", _fail)
    monkeypatch.setattr("src.engine.providers.OllamaProvider", _fail)
    monkeypatch.setattr("src.engine.providers.CloudProvider", _fail)

    result = CliRunner().invoke(cli, ["route", "oi"])

    assert result.exit_code == 0
    assert "rota: local" in result.output


def test_route_nao_ecoa_o_pedido() -> None:
    secret = "TEXTO_SECRETO_NAO_DEVE_APARECER_42"
    result = CliRunner().invoke(cli, ["route", secret])

    assert result.exit_code == 0
    assert secret not in result.output


def test_route_vazio_sai_com_erro() -> None:
    result = CliRunner().invoke(cli, ["route", "   "])

    assert result.exit_code != 0


def test_route_frase_pesada_nao_ecoa_needle_nem_pedido() -> None:
    segredo = "CHAVE_SECRETA_NAO_DEVE_APARECER"
    result = CliRunner().invoke(
        cli,
        ["route", f"Pensa mais sobre {segredo}"],
    )

    assert result.exit_code == 0
    assert segredo not in result.output
    assert "pensa mais" not in result.output
    assert "frase explícita (lista YBY_HEAVY_PHRASES)" in result.output


def test_route_config_invalida_yby_heavy_min_chars(monkeypatch) -> None:
    def _fail():
        raise AssertionError("motor")

    monkeypatch.setattr("src.main.build_engine", _fail)

    result = CliRunner().invoke(
        cli,
        ["route", "oi"],
        env={"YBY_HEAVY_MIN_CHARS": "muitos"},
    )

    assert result.exit_code == 1
    assert "YBY_HEAVY_MIN_CHARS" in result.output
    assert "muitos" in result.output
    assert "Traceback" not in result.output