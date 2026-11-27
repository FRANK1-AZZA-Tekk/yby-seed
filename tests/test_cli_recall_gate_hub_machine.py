"""CLI `recall`, `gate`, `hub --once` e `machine`: offline e determinísticos.

Estratégia:
- `socket.socket.connect` é bloqueado em todos os testes do arquivo; qualquer
  tentativa de rede falha o teste.
- Ollama é sempre um fake (`requests.get` do hub, `OllamaProvider` do translator).
- Vault, saída do PWA e log do hub ficam em `tmp_path`; `.env` nunca é lido.
- `subprocess` é trocado por uma armadilha: `gate` não pode executar nada.
"""

from __future__ import annotations

import json
import logging
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest
import requests
from click.testing import CliRunner

from src.main import cli
from src.memory.vault import Vault
from src.yby_machine.fallback import fallback_spec_from_prompt

_PEDIDO = "controle de encomendas com Pix"


@pytest.fixture(autouse=True)
def _offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def _bloqueado(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("rede bloqueada nos testes de CLI")

    monkeypatch.setattr(socket.socket, "connect", _bloqueado)
    monkeypatch.setattr("src.main.load_dotenv", lambda *args, **kwargs: False)
    for name in (
        "YBY_VAULT_PATH",
        "YBY_OLLAMA_BASE_URL",
        "YBY_MACHINE_TRANSLATOR",
        "YBY_HUB_LOG",
        "YBY_HUB_INTERVAL",
        "YBY_HUB_TIMEOUT",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def _sem_execucao(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    chamadas: list[Any] = []

    def _armadilha(*args: Any, **_kwargs: Any) -> None:
        chamadas.append(args)
        raise AssertionError("o gate não pode executar comandos")

    monkeypatch.setattr(subprocess, "run", _armadilha)
    monkeypatch.setattr(subprocess, "Popen", _armadilha)
    return chamadas


@pytest.fixture
def _log_do_hub(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Aponta o log do hub para tmp_path e restaura o logging raiz depois."""

    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    monkeypatch.setenv("YBY_HUB_LOG", str(tmp_path / "hub.log"))
    yield tmp_path / "hub.log"
    for handler in list(root.handlers):
        if handler not in handlers:
            handler.close()
    root.handlers[:] = handlers
    root.setLevel(level)


# --- recall ------------------------------------------------------------------


def test_recall_encontra_nota_do_vault(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    vault = Vault(tmp_path / "vault")
    vault.write_note("receitas/bolo", "bolo de cenoura com cobertura de chocolate")
    vault.write_note("trabalho/reuniao", "reunião semanal sobre orçamento")
    monkeypatch.setenv("YBY_VAULT_PATH", str(tmp_path / "vault"))

    result = CliRunner().invoke(cli, ["recall", "bolo de cenoura"])

    assert result.exit_code == 0, result.output
    assert "receitas/bolo.md" in result.output
    assert "trabalho/reuniao.md" not in result.output
    score = result.output.split()[0]
    assert 0 < float(score) <= 1.0001


def test_recall_sem_resultado_informa_ausencia(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    Vault(tmp_path / "vault").write_note("receitas/bolo", "bolo de cenoura")
    monkeypatch.setenv("YBY_VAULT_PATH", str(tmp_path / "vault"))

    result = CliRunner().invoke(cli, ["recall", "astronomia quantica"])

    assert result.exit_code == 0
    assert result.output.strip() == "Nenhuma nota."


def test_recall_vault_vazio_informa_ausencia(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("YBY_VAULT_PATH", str(tmp_path / "novo-vault"))

    result = CliRunner().invoke(cli, ["recall", "qualquer coisa"])

    assert result.exit_code == 0
    assert result.output.strip() == "Nenhuma nota."


@pytest.mark.parametrize("valor", [None, "", "   "])
def test_recall_sem_vault_configurado_falha_de_forma_controlada(
    monkeypatch: pytest.MonkeyPatch, valor: str | None
) -> None:
    if valor is not None:
        monkeypatch.setenv("YBY_VAULT_PATH", valor)

    result = CliRunner().invoke(cli, ["recall", "bolo"])

    assert result.exit_code == 1
    assert "defina YBY_VAULT_PATH" in result.stderr
    assert result.stdout == ""
    assert isinstance(result.exception, SystemExit)


def test_recall_indice_corrompido_e_reconstruido(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    vault = Vault(tmp_path / "vault")
    vault.write_note("receitas/bolo", "bolo de cenoura")
    vault.index_path.write_text("{ isto não é json", encoding="utf-8")
    monkeypatch.setenv("YBY_VAULT_PATH", str(tmp_path / "vault"))

    result = CliRunner().invoke(cli, ["recall", "bolo"])

    assert result.exit_code == 0, result.output
    assert "receitas/bolo.md" in result.output
    assert json.loads(vault.index_path.read_text(encoding="utf-8"))["notes"]


# --- gate --------------------------------------------------------------------


def test_gate_comando_permitido_retorna_run(_sem_execucao: list[Any]) -> None:
    result = CliRunner().invoke(cli, ["gate", "ls", "-la"])

    assert result.exit_code == 0
    assert result.output.startswith("run:")
    assert _sem_execucao == []


def test_gate_comando_sensivel_retorna_ask_e_pede_confirmacao(
    _sem_execucao: list[Any],
) -> None:
    result = CliRunner().invoke(cli, ["gate", "git", "commit", "-m", "x"], input="s\n")

    assert result.exit_code == 0
    assert result.output.startswith("ask:")
    assert "Executar `git commit -m x`? [s/n]" in result.output
    assert "Não executado." not in result.output
    assert _sem_execucao == []


def test_gate_ask_com_confirmacao_negativa_sai_com_erro_sem_executar(
    _sem_execucao: list[Any],
) -> None:
    result = CliRunner().invoke(cli, ["gate", "rm", "arquivo.txt"], input="n\n")

    assert result.exit_code == 1
    assert result.output.startswith("ask:")
    assert "[s/n]" in result.output
    assert "Não executado." in result.output
    assert _sem_execucao == []


def test_gate_ask_sem_resposta_nao_aprova(_sem_execucao: list[Any]) -> None:
    result = CliRunner().invoke(cli, ["gate", "rm", "arquivo.txt"], input="")

    assert result.exit_code != 0
    assert "Não executado." not in result.output
    assert _sem_execucao == []


@pytest.mark.parametrize("comando", [["rm", "-rf", "/"], ["git", "push", "--force", "origin"]])
def test_gate_comando_proibido_retorna_refuse_sem_perguntar(
    comando: list[str], _sem_execucao: list[Any]
) -> None:
    result = CliRunner().invoke(cli, ["gate", *comando], input="s\n")

    assert result.exit_code == 1
    assert result.output.startswith("refuse:")
    assert "[s/n]" not in result.output
    assert "Executar" not in result.output
    assert _sem_execucao == []


# --- hub --once --------------------------------------------------------------


class _Resposta:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _fake_get(monkeypatch: pytest.MonkeyPatch, *, status: int | Exception) -> list[dict[str, Any]]:
    chamadas: list[dict[str, Any]] = []

    def _get(url: str, **kwargs: Any) -> _Resposta:
        chamadas.append({"url": url, **kwargs})
        if isinstance(status, Exception):
            raise status
        return _Resposta(status)

    monkeypatch.setattr("src.platform.hub.requests.get", _get)
    return chamadas


@pytest.fixture
def _sem_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    def _proibido(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("--once não pode entrar no loop")

    monkeypatch.setattr("src.platform.hub.run_loop", _proibido)
    monkeypatch.setattr("src.platform.hub.time.sleep", _proibido)


def test_hub_once_com_ollama_disponivel_retorna_sucesso(
    monkeypatch: pytest.MonkeyPatch, _log_do_hub: Path, _sem_loop: None
) -> None:
    chamadas = _fake_get(monkeypatch, status=200)

    result = CliRunner().invoke(cli, ["hub", "--once"])

    assert result.exit_code == 0, result.output
    assert len(chamadas) == 1
    assert chamadas[0]["url"] == "http://127.0.0.1:11434/api/tags"
    assert "ollama=ok" in _log_do_hub.read_text(encoding="utf-8")


def test_hub_once_com_ollama_indisponivel_falha_de_forma_controlada(
    monkeypatch: pytest.MonkeyPatch, _log_do_hub: Path, _sem_loop: None
) -> None:
    chamadas = _fake_get(monkeypatch, status=requests.ConnectionError("recusada"))

    result = CliRunner().invoke(cli, ["hub", "--once"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert len(chamadas) == 1
    log = _log_do_hub.read_text(encoding="utf-8")
    assert "ollama falhou: indisponível" in log
    assert "recusada" in log


def test_hub_once_com_erro_http_falha_de_forma_controlada(
    monkeypatch: pytest.MonkeyPatch, _log_do_hub: Path, _sem_loop: None
) -> None:
    _fake_get(monkeypatch, status=503)

    result = CliRunner().invoke(cli, ["hub", "--once"])

    assert result.exit_code == 1
    assert "ollama falhou: HTTP 503" in _log_do_hub.read_text(encoding="utf-8")


def test_hub_once_respeita_url_do_ambiente_e_recusa_host_remoto(
    monkeypatch: pytest.MonkeyPatch, _log_do_hub: Path, _sem_loop: None
) -> None:
    chamadas = _fake_get(monkeypatch, status=200)
    monkeypatch.setenv("YBY_OLLAMA_BASE_URL", "http://ollama.exemplo.com:11434")

    result = CliRunner().invoke(cli, ["hub", "--once"])

    assert result.exit_code == 2
    assert chamadas == []
    assert "loopback" in _log_do_hub.read_text(encoding="utf-8")


# --- machine -----------------------------------------------------------------


class _ProviderProibido:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("--fallback-only não pode criar provider Ollama")


def _fake_provider(*, resposta: str | Exception) -> type:
    class _Provider:
        chamadas: list[str] = []
        fechado = False

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def complete(self, prompt: str, *, model: str, system: str, **_kwargs: Any) -> str:
            type(self).chamadas.append(prompt)
            if isinstance(resposta, Exception):
                raise resposta
            return resposta

        def close(self) -> None:
            type(self).fechado = True

    return _Provider


_ARQUIVOS_PWA = {"index.html", "styles.css", "app.js"}


def test_machine_fallback_only_grava_pwa_sem_ollama(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("src.yby_machine.translator.OllamaProvider", _ProviderProibido)
    saida = tmp_path / "pwa"

    result = CliRunner().invoke(cli, ["machine", "--fallback-only", "-o", str(saida), _PEDIDO])

    assert result.exit_code == 0, result.output
    assert "origem: fallback" in result.stderr
    assert f"em {saida}" in result.stderr
    gravados = {path.name for path in saida.iterdir()}
    assert _ARQUIVOS_PWA <= gravados
    assert "<html" in (saida / "index.html").read_text(encoding="utf-8").casefold()
    assert (saida / "app.js").read_text(encoding="utf-8").strip()
    assert f"arquivos: {len(gravados)} em" in result.stderr


def test_machine_saida_fica_so_na_pasta_informada(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    saida = tmp_path / "a" / "b" / "pwa"

    result = CliRunner().invoke(cli, ["machine", "--fallback-only", "--out", str(saida), _PEDIDO])

    assert result.exit_code == 0, result.output
    assert _ARQUIVOS_PWA <= {path.name for path in saida.iterdir()}
    assert [path.name for path in tmp_path.iterdir()] == ["a"]


def test_machine_com_ollama_valido_usa_a_spec_do_modelo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    spec = fallback_spec_from_prompt(_PEDIDO)
    provider = _fake_provider(resposta=spec.model_dump_json())
    monkeypatch.setattr("src.yby_machine.translator.OllamaProvider", provider)
    saida = tmp_path / "pwa"

    result = CliRunner().invoke(cli, ["machine", "-o", str(saida), _PEDIDO])

    assert result.exit_code == 0, result.output
    assert "origem: ollama" in result.stderr
    assert provider.chamadas == [_PEDIDO]
    assert provider.fechado is True
    assert _ARQUIVOS_PWA <= {path.name for path in saida.iterdir()}


@pytest.mark.parametrize(
    "resposta",
    [
        pytest.param(OSError("conexão recusada"), id="ollama-indisponivel"),
        pytest.param("isto não é JSON", id="resposta-invalida"),
        pytest.param("", id="resposta-vazia"),
    ],
)
def test_machine_falha_do_modelo_cai_no_fallback_e_ainda_grava(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resposta: str | Exception
) -> None:
    provider = _fake_provider(resposta=resposta)
    monkeypatch.setattr("src.yby_machine.translator.OllamaProvider", provider)
    saida = tmp_path / "pwa"

    result = CliRunner().invoke(cli, ["machine", "-o", str(saida), _PEDIDO])

    assert result.exit_code == 0, result.output
    assert "origem: fallback" in result.stderr
    assert provider.chamadas == [_PEDIDO]
    assert provider.fechado is True
    assert _ARQUIVOS_PWA <= {path.name for path in saida.iterdir()}


def test_machine_pedido_vazio_falha_sem_gravar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("src.yby_machine.translator.OllamaProvider", _ProviderProibido)
    saida = tmp_path / "pwa"

    result = CliRunner().invoke(cli, ["machine", "-o", str(saida), "   "])

    assert result.exit_code == 1
    assert "Informe um pedido" in result.stderr
    assert not saida.exists()
