"""Smoke: painel lê writers reais (audit + incidents + develop.save_plan)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.develop.schemas import DevelopPlan, Layer
from src.develop.store import save_plan
from src.painel.app import create_app

TOKEN = "smoke-painel-writers"


def test_painel_le_writers_reais_nos_paths(tmp_path: Path) -> None:
    state = tmp_path / "yby-seed"
    audit = state / "assist-audit.jsonl"
    reminders = state / "assist-reminders.json"
    incidents = state / "sentinel" / "incidents.json"
    develop_root = state / "develop"
    incidents.parent.mkdir(parents=True)
    state.mkdir(parents=True, exist_ok=True)

    audit.write_text(
        json.dumps(
            {
                "timestamp": 1_700_000_000.0,
                "tool": "routine.run",
                "ok": False,
                "error": "step falhou",
                "meta": {
                    "name": "manha",
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
    reminders.write_text("[]", encoding="utf-8")
    incidents.write_text(
        json.dumps(
            [
                {
                    "id": "inc-smoke",
                    "rule": "ollama_down",
                    "state": "active",
                    "notified_at": 1_700_000_100.0,
                    "message": "Ollama sem resposta",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    plan = DevelopPlan(
        id="smoke-plan",
        pedido="smoke",
        base_commit="deadbeef",
        layers=[
            Layer(
                id="L1",
                depends_on=[],
                objetivo="camada enviada",
                allowed_files=["src/main.py"],
                status="enviada",
            )
        ],
    )
    save_plan(plan, root=develop_root)

    app = create_app(
        token=TOKEN,
        state_dir=state,
        audit_path=audit,
        reminders_path=reminders,
        incidents_path=incidents,
        develop_plans_dir=develop_root / "plans",
        ollama_probe=lambda: "ok",
    )
    client = TestClient(app)

    denied = client.get("/api/resumo")
    assert denied.status_code == 401
    assert "routines" not in denied.json()

    ok = client.get("/api/resumo", headers={"Authorization": f"Bearer {TOKEN}"})
    assert ok.status_code == 200
    data = ok.json()
    assert data["routines"][0]["state"] == "falhou"
    assert data["routines"][0]["meta"]["partial"] is True
    assert data["alerts"][0]["title"] == "ollama_down"
    assert data["alerts"][0]["state"] == "falhou"
    layers = {x["title"]: x["state"] for x in data["develop_layers"]}
    assert layers["smoke-plan/L1"] == "aguardando_aprovacao"

    html = client.get("/", headers={"X-API-Token": TOKEN})
    assert html.status_code == 200
    assert "falhou" in html.text
    assert "aguardando_aprovacao" in html.text
    assert "manha" in html.text
