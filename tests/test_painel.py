"""Testes do painel local (auth, estados, escape XSS, bind)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.painel.app import assert_loopback_host, create_app


TOKEN = "painel-test-token-xyz"


def _write_fixtures(tmp: Path) -> dict[str, Path]:
    audit = tmp / "assist-audit.jsonl"
    reminders = tmp / "assist-reminders.json"
    incidents = tmp / "sentinel" / "incidents.json"
    plans = tmp / "develop" / "plans"
    plans.mkdir(parents=True)
    incidents.parent.mkdir(parents=True)

    audit.write_text(
        json.dumps(
            {
                "timestamp": 1_700_000_000.0,
                "tool": "routine.run",
                "ok": False,
                "error": "step falhou",
                "meta": {
                    "name": "manha",
                    "keys": ["ran", "failed", "skipped", "name"],
                    "ran": ["open.url"],
                    "failed": ["app.launch"],
                    "skipped": ["notify"],
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    reminders.write_text(
        json.dumps(
            [
                {
                    "id": "r1",
                    "text": '<script>alert("xss")</script> tomar agua',
                    "when_iso": "2024-01-01T12:00:00+00:00",
                    "tz": "UTC",
                    "delivered": False,
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    incidents.write_text(
        json.dumps(
            [
                {
                    "id": "inc-1",
                    "rule": "ollama_down",
                    "state": "active",
                    "notified_at": 1_700_000_100.0,
                    "message": "Ollama sem resposta",
                },
                {
                    "id": "inc-2",
                    "rule": "old",
                    "state": "resolved",
                    "notified_at": 1_700_000_050.0,
                    "message": "já resolvido",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    (plans / "plan-a.json").write_text(
        json.dumps(
            {
                "id": "plan-a",
                "updated_at": 1_700_000_200.0,
                "layers": [
                    {"id": "L1", "status": "enviada"},
                    {"id": "L0", "status": "aceita"},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "audit": audit,
        "reminders": reminders,
        "incidents": incidents,
        "plans": plans,
    }


def _client(tmp: Path) -> TestClient:
    paths = _write_fixtures(tmp)
    app = create_app(
        token=TOKEN,
        audit_path=paths["audit"],
        reminders_path=paths["reminders"],
        incidents_path=paths["incidents"],
        develop_plans_dir=paths["plans"],
        ollama_probe=lambda: "ok",
    )
    return TestClient(app)


def test_sem_token_configurado_503(tmp_path: Path) -> None:
    app = create_app(token="", ollama_probe=lambda: "ok", state_dir=tmp_path)
    client = TestClient(app)
    r = client.get("/api/resumo")
    assert r.status_code == 503
    assert "error" in r.json()


def test_token_errado_401_sem_dados(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/resumo", headers={"X-API-Token": "errado"})
    assert r.status_code == 401
    body = r.json()
    assert "routines" not in body
    assert "error" in body


def test_sem_header_401(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/")
    assert r.status_code == 401


def test_autenticado_tres_estados_distintos(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get(
        "/api/resumo",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ollama"] == "ok"

    assert len(data["routines"]) == 1
    routine = data["routines"][0]
    assert routine["state"] == "falhou"
    assert routine["meta"]["partial"] is True
    assert routine["meta"]["ran"] == ["open.url"]
    assert routine["meta"]["skipped"] == ["notify"]

    assert len(data["alerts"]) == 1
    assert data["alerts"][0]["state"] == "falhou"
    assert data["alerts"][0]["title"] == "ollama_down"

    layers = {x["title"]: x["state"] for x in data["develop_layers"]}
    assert layers["plan-a/L1"] == "aguardando_aprovacao"
    assert layers["plan-a/L0"] == "executado"

    states = {
        routine["state"],
        data["alerts"][0]["state"],
        layers["plan-a/L1"],
    }
    assert states == {"falhou", "aguardando_aprovacao"} or "falhou" in states
    assert "aguardando_aprovacao" in states


def test_html_escapa_xss_e_mostra_estados(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/", headers={"X-API-Token": TOKEN})
    assert r.status_code == 200
    text = r.text
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "falhou" in text
    assert "aguardando_aprovacao" in text
    assert "ollama_down" in text
    assert "manha" in text


def test_bind_rejeita_nao_loopback() -> None:
    assert assert_loopback_host("127.0.0.1") == "127.0.0.1"
    assert assert_loopback_host("localhost") == "127.0.0.1"
    with pytest.raises(ValueError):
        assert_loopback_host("0.0.0.0")
    with pytest.raises(ValueError):
        assert_loopback_host("192.168.1.1")


def test_audit_routine_meta_ran_skipped(tmp_path: Path) -> None:
    """Diff mínimo: executor grava ran/failed/skipped no meta de routine.run."""

    from src.assist.config import AssistConfig
    from src.assist.executor import _audit
    from src.assist.types import ToolResult

    audit = tmp_path / "a.jsonl"
    cfg = AssistConfig(
        apps={},
        search_roots=(),
        routines={},
        reminders_path=tmp_path / "r.json",
        audit_log_path=audit,
        ollama_base_url="http://127.0.0.1:11434",
        ollama_timeout=1.0,
    )
    _audit(
        cfg,
        ToolResult(
            tool="routine.run",
            ok=False,
            data={
                "name": "t",
                "ran": ["a"],
                "failed": ["b"],
                "skipped": ["c"],
            },
            error="boom",
        ),
    )
    event = json.loads(audit.read_text(encoding="utf-8").strip())
    assert event["meta"]["ran"] == ["a"]
    assert event["meta"]["failed"] == ["b"]
    assert event["meta"]["skipped"] == ["c"]
