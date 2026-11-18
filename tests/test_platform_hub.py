"""Hub keepalive da plataforma."""

from __future__ import annotations

import requests

from src.platform.hub import check_ollama, main, run_loop, warmup_ollama


class _Resp:
    def __init__(self, status: int) -> None:
        self.status_code = status


class _Session:
    def __init__(self, response: _Resp | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.urls: list[str] = []
        self.posts: list[dict[str, object]] = []

    def get(self, url: str, **_kwargs: object) -> _Resp:
        self.urls.append(url)
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response

    def post(self, url: str, **kwargs: object) -> _Resp:
        self.posts.append({"url": url, **kwargs})
        if self.error:
            raise self.error
        return _Resp(200)


def test_check_ollama_ok() -> None:
    session = _Session(_Resp(200))
    assert check_ollama("http://127.0.0.1:11434", timeout=1, session=session) == "ok"
    assert session.urls == ["http://127.0.0.1:11434/api/tags"]


def test_check_ollama_erro() -> None:
    session = _Session(error=requests.ConnectionError("down"))
    status = check_ollama("http://127.0.0.1:11434", timeout=1, session=session)
    assert "indisponível" in status


def test_run_loop_once() -> None:
    code = run_loop(
        base_url="http://127.0.0.1:9",
        interval=1.0,
        timeout=0.1,
        max_ticks=1,
    )
    assert code == 0


def test_main_once(monkeypatch) -> None:
    monkeypatch.setenv("YBY_OLLAMA_BASE_URL", "http://127.0.0.1:9")
    assert main(["--once"]) == 0


def test_warmup_posta_generate_com_num_predict_1() -> None:
    session = _Session(_Resp(200))
    assert (
        warmup_ollama(
            "http://127.0.0.1:11434",
            model="qwen2.5-coder:3b",
            timeout=1,
            session=session,
            num_predict=1,
        )
        == "ok"
    )
    assert len(session.posts) == 1
    payload = session.posts[0]["json"]
    assert isinstance(payload, dict)
    assert payload["options"]["num_predict"] == 1


def test_run_loop_warmup_uma_vez(monkeypatch) -> None:
    monkeypatch.setenv("YBY_HUB_WARMUP", "1")
    session = _Session(_Resp(200))
    code = run_loop(
        base_url="http://127.0.0.1:11434",
        interval=0.01,
        timeout=1,
        max_ticks=2,
        session=session,
        warmup=True,
        local_model="m",
    )
    assert code == 0
    assert len(session.posts) == 1
