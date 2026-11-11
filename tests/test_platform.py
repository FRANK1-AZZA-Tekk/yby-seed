"""Fase P: systemd de usuário, keepalive e loopback."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

import pytest
import requests

from src.platform import hub


class _Resp:
    def __init__(self, status: int) -> None:
        self.status_code = status


class _Session:
    def __init__(self, response: _Resp | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.posted: list[dict[str, object]] = []

    def get(self, url: str, **_kwargs: object) -> _Resp:
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response

    def post(self, url: str, **kwargs: object) -> _Resp:
        self.posted.append({"url": url, **kwargs})
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


def test_ollama_ping_inclui_keep_alive_e_num_ctx() -> None:
    session = _Session(_Resp(200))
    hub.check_ollama(
        "http://127.0.0.1:11434",
        timeout=1,
        session=session,
        keep_alive="30m",
        num_ctx=4096,
    )
    assert len(session.posted) == 1
    payload = session.posted[0]["json"]
    assert payload["keep_alive"] == "30m"
    assert payload["options"]["num_ctx"] == 4096
    assert session.posted[0]["url"].endswith("/api/generate")


def test_ollama_falha_registrada_no_log(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="yby.hub")
    session = _Session(error=requests.ConnectionError("down"))
    hub.run_loop(
        base_url="http://127.0.0.1:9",
        interval=1.0,
        timeout=0.1,
        max_ticks=1,
        session=session,
    )
    assert any("ollama falhou" in r.message for r in caplog.records)


def test_url_ollama_so_loopback() -> None:
    assert hub.is_loopback_ollama_url("http://127.0.0.1:11434") is True
    assert hub.is_loopback_ollama_url("http://localhost:11434/") is True
    assert hub.is_loopback_ollama_url("http://192.168.1.10:11434") is False


def test_main_recusa_ollama_fora_do_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YBY_OLLAMA_BASE_URL", "http://203.0.113.1:11434")
    assert hub.main(["--once"]) == 2


def test_hub_nao_expoe_porta() -> None:
    assert not hasattr(hub, "start_server")
    assert "uvicorn" not in Path(hub.__file__).read_text(encoding="utf-8")
    assert "listen(" not in Path(hub.__file__).read_text(encoding="utf-8")


def test_install_gera_unit_systemd_usuario(repo_root: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home)}
    result = subprocess.run(
        ["bash", str(repo_root / "scripts/install-hub-service.sh")],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    unit = home / ".config/systemd/user/yby-hub.service"
    assert unit.is_file()
    text = unit.read_text(encoding="utf-8")
    assert "After=network-online.target" in text
    assert "Wants=network-online.target" in text
    assert f"WorkingDirectory={repo_root}" in text
    assert "Restart=on-failure" in text
    assert "RestartSec=10" in text
    env_file = home / ".config/yby-seed/.env"
    assert f"EnvironmentFile=-{env_file}" in text
    assert f"{repo_root}/.env" not in text


def test_keepalive_permanece_ativo_com_ollama_off() -> None:
    code = hub.run_loop(
        base_url="http://127.0.0.1:65510",
        interval=0.01,
        timeout=0.05,
        max_ticks=2,
        session=_Session(error=requests.ConnectionError("down")),
    )
    assert code == 0


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_security_doc_menciona_limitacao_ast(repo_root: Path) -> None:
    text = (repo_root / "docs/SECURITY.md").read_text(encoding="utf-8")
    assert "Limitação conhecida do AST guard" in text
    assert "chr()" in text
    assert "sandbox.py" in text
