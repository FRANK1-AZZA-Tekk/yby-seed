"""Lote 21: pesquisa consentida + HTTP fake (sem rede)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from src.main import cli
from src.memory.prefs import set_pref
from src.memory.vault import Vault
from src.research.consent import ResearchError, resolve_consent
from src.research.fake_http import FakeHttpClient
from src.research.search import search


def test_sem_consent_bloqueia() -> None:
    with pytest.raises(ResearchError, match="consentimento"):
        search("ollama local", consented=False)


def test_com_consent_retorna_fake() -> None:
    report = search("ollama local", consented=True)
    assert report.transport == "fake"
    assert "sem busca real" in report.warning.casefold() or "fake" in report.warning.casefold()
    assert len(report.hits) >= 2
    assert all(h.url.startswith("https://fake.yby.local/") for h in report.hits)
    assert "ollama" in report.query.casefold()


def test_pref_allow_web_search(tmp_path: Path) -> None:
    vault = Vault(tmp_path)
    set_pref(vault, "allow_web_search", "1", consent=True)
    assert resolve_consent(flag_consent=False, vault=vault) is True
    report = search("vault sync", consented=False, vault=vault)
    assert report.transport == "fake"
    assert report.hits


def test_query_com_segredo_bloqueada() -> None:
    with pytest.raises(ResearchError, match="segredo"):
        search(
            "chave sk-or-v1-abcdefghijklmnopqrstuvwxyz012345",
            consented=True,
        )


def test_fake_client_nao_usa_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a, **_k):
        raise AssertionError("requests não deve ser chamado")

    monkeypatch.setitem(sys.modules, "requests", type(sys)("requests"))
    monkeypatch.setattr(sys.modules["requests"], "get", boom, raising=False)
    monkeypatch.setattr(sys.modules["requests"], "Session", boom, raising=False)
    client = FakeHttpClient()
    response = client.get("https://fake.yby.local/search?q=teste")
    assert response.status_code == 200
    report = search("teste", consented=True, client=client)
    assert report.transport == "fake"


def test_cli_research(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YBY_VAULT_PATH", str(tmp_path))
    runner = CliRunner()
    denied = runner.invoke(cli, ["research", "qwen modelo"])
    assert denied.exit_code == 1
    assert "consentimento" in denied.output.lower()

    ok = runner.invoke(cli, ["research", "qwen modelo", "--consent"])
    assert ok.exit_code == 0, ok.output
    assert "transport: fake" in ok.output
    assert "fake.yby.local" in ok.output

    set_pref(Vault(tmp_path), "allow_web_search", "1", consent=True)
    via_pref = runner.invoke(cli, ["research", "via pref"])
    assert via_pref.exit_code == 0, via_pref.output
    assert "transport: fake" in via_pref.output

    as_json = runner.invoke(cli, ["research", "json", "--consent", "--json"])
    assert as_json.exit_code == 0
    assert '"transport": "fake"' in as_json.output
