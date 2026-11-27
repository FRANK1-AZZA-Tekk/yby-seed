"""Testes 100% offline dos endpoints do Cockpit PhoneBox (`/api/v1/cockpit/*`)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.yby.app import create_mesh_app
from src.yby.audio.mqtt_bus import InMemoryMqttBus
from src.yby.cockpit import (
    CockpitService,
    ServiceHealth,
    create_cockpit_app,
)
from src.yby.obsidian_rag import (
    InMemoryObsidianStore,
    ObsidianVaultIndexer,
    parse_obsidian_markdown,
)
from src.yby_machine.fallback import fallback_spec_from_prompt
from src.yby_machine.store import InMemorySpecStore


def _fixed_clock() -> datetime:
    return datetime(2026, 11, 26, 14, 35, 0, tzinfo=timezone.utc)


def _ok_probes() -> dict[str, object]:
    async def _up() -> ServiceHealth:
        return ServiceHealth(status="up", latency_ms=1.2, detail="local-mock")

    return {
        "redis": _up,
        "postgres_pgvector": _up,
        "mqtt": _up,
    }


@pytest.mark.asyncio
async def test_cockpit_status_compact_counts_and_degraded_state(tmp_path: Path) -> None:
    spec_store = InMemorySpecStore()
    await spec_store.save(
        prompt="App de encomendas",
        embedding=[0.1] * 8,
        spec=fallback_spec_from_prompt("App de encomendas"),
        source="fallback",
    )
    await spec_store.save(
        prompt="Controle de oficina",
        embedding=[0.2] * 8,
        spec=fallback_spec_from_prompt("Controle de oficina"),
        source="fallback",
    )

    service = CockpitService(
        vault_path=tmp_path,
        indexer=ObsidianVaultIndexer(store=InMemoryObsidianStore()),
        mqtt_bus=InMemoryMqttBus(),
        spec_store=spec_store,
        service_probes=_ok_probes(),  # type: ignore[arg-type]
        clock=_fixed_clock,
    )
    client = TestClient(create_cockpit_app(service=service, expected_token=""))

    resp = client.get("/api/v1/cockpit/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["services"]["fastapi"]["status"] == "up"
    assert body["services"]["redis"]["status"] == "up"
    assert body["services"]["postgres_pgvector"]["status"] == "up"
    assert body["services"]["mqtt"]["status"] == "up"
    assert body["yby_machine_specs_count"] == 2
    assert body["active_tasks"] == 0
    assert body["pending_edge_events"] == 0

    # Quando um serviço configurado cai, status global sinaliza "degraded".
    async def _down() -> ServiceHealth:
        return ServiceHealth(status="down", latency_ms=5.0, detail="connection refused")

    degraded_probes = dict(_ok_probes())
    degraded_probes["redis"] = _down
    degraded_service = CockpitService(
        vault_path=tmp_path,
        indexer=ObsidianVaultIndexer(store=InMemoryObsidianStore()),
        service_probes=degraded_probes,  # type: ignore[arg-type]
        clock=_fixed_clock,
    )
    degraded_client = TestClient(create_cockpit_app(service=degraded_service, expected_token=""))
    degraded_resp = degraded_client.get("/api/v1/cockpit/status")
    assert degraded_resp.status_code == 200
    assert degraded_resp.json()["status"] == "degraded"
    assert degraded_resp.json()["services"]["redis"]["status"] == "down"


def test_cockpit_webhook_capture_inbox_reindex_and_mqtt(tmp_path: Path) -> None:
    mqtt = InMemoryMqttBus()
    indexer = ObsidianVaultIndexer(store=InMemoryObsidianStore())
    service = CockpitService(
        vault_path=tmp_path,
        indexer=indexer,
        mqtt_bus=mqtt,
        service_probes=_ok_probes(),  # type: ignore[arg-type]
        clock=_fixed_clock,
    )
    client = TestClient(create_cockpit_app(service=service, expected_token=""))

    # 1) capture_inbox cria 00-inbox/2026-11-26.md em Obsidian Flavored Markdown.
    cap_1 = client.post(
        "/api/v1/cockpit/webhook",
        json={
            "action": "capture_inbox",
            "title": "Ideia Wearables",
            "note": "Sincronizar alerta háptico no [[t-watch-s3-plus]] via [[pc-hub]].",
            "tags": ["phonebox", "wearables"],
        },
    )
    assert cap_1.status_code == 200
    cap_1_json = cap_1.json()
    assert cap_1_json["ok"] is True
    assert cap_1_json["data"]["relative_path"] == "00-inbox/2026-11-26.md"
    assert cap_1_json["data"]["created"] is True

    # Segunda captura no mesmo dia apenas anexa entrada.
    cap_2 = client.post(
        "/api/v1/cockpit/webhook",
        json={
            "action": "capture_inbox",
            "note": "Checar consumo de VRAM no Moto Edge 30.",
        },
    )
    assert cap_2.status_code == 200
    assert cap_2.json()["data"]["created"] is False

    inbox_file = tmp_path / "00-inbox" / "2026-11-26.md"
    inbox_text = inbox_file.read_text(encoding="utf-8")
    parsed_inbox = parse_obsidian_markdown(inbox_text, source_path="00-inbox/2026-11-26.md")
    assert parsed_inbox.frontmatter["type"] == "inbox"
    assert "t-watch-s3-plus" in parsed_inbox.wikilinks
    assert "wearables" in parsed_inbox.tags
    assert "Checar consumo de VRAM" in parsed_inbox.body

    # 2) trigger_reindex indexa incrementalmente o cofre e atualiza contagem em /status.
    reindex_1 = client.post(
        "/api/v1/cockpit/webhook",
        json={"action": "trigger_reindex"},
    )
    assert reindex_1.status_code == 200
    r1_data = reindex_1.json()["data"]
    assert r1_data["files_indexed"] == 1
    assert r1_data["chunks_upserted"] >= 1

    reindex_2 = client.post(
        "/api/v1/cockpit/webhook",
        json={"action": "trigger_reindex"},
    )
    assert reindex_2.status_code == 200
    assert reindex_2.json()["data"]["files_indexed"] == 0
    assert reindex_2.json()["data"]["files_skipped"] == 1

    status_after = client.get("/api/v1/cockpit/status").json()
    assert status_after["indexed_chunks"] == r1_data["total_chunks"]

    # 3) publish_mqtt publica envelope JSON seguro no tópico local yby/cockpit/action.
    mqtt_resp = client.post(
        "/api/v1/cockpit/webhook",
        json={
            "action": "publish_mqtt",
            "mqtt_payload": {"target": "t-watch-s3-plus", "cmd": "vibrate", "pattern": "short"},
        },
    )
    assert mqtt_resp.status_code == 200
    assert mqtt_resp.json()["data"]["topic"] == "yby/cockpit/action"
    assert len(mqtt.messages) == 1
    assert mqtt.messages[0].topic == "yby/cockpit/action"
    assert mqtt.messages[0].qos == 1
    published = json.loads(mqtt.messages[0].payload)
    assert published["payload"]["cmd"] == "vibrate"
    assert published["source"] == "phonebox-edge30"

    # Validação Pydantic rejeita payload vazio ou tópico fora do prefixo seguro.
    assert (
        client.post("/api/v1/cockpit/webhook", json={"action": "capture_inbox"}).status_code == 422
    )
    assert (
        client.post("/api/v1/cockpit/webhook", json={"action": "publish_mqtt"}).status_code == 422
    )
    assert (
        client.post(
            "/api/v1/cockpit/webhook",
            json={
                "action": "publish_mqtt",
                "mqtt_topic": "system/shutdown",
                "mqtt_payload": {"cmd": "halt"},
            },
        ).status_code
        == 422
    )


def test_cockpit_optional_token_auth_and_mesh_app_integration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CockpitService(
        vault_path=tmp_path,
        indexer=ObsidianVaultIndexer(store=InMemoryObsidianStore()),
        mqtt_bus=InMemoryMqttBus(),
        service_probes=_ok_probes(),  # type: ignore[arg-type]
        clock=_fixed_clock,
    )

    # Sem YBY_COCKPIT_TOKEN configurado -> webhook local permitido sem header.
    monkeypatch.delenv("YBY_COCKPIT_TOKEN", raising=False)
    app_open = create_mesh_app(cockpit_service=service)
    client_open = TestClient(app_open)

    health = client_open.get("/health")
    assert health.status_code == 200
    assert health.json()["modules"]["cockpit"] is True

    open_resp = client_open.post(
        "/api/v1/cockpit/webhook",
        json={"action": "trigger_reindex"},
    )
    assert open_resp.status_code == 200

    # Com YBY_COCKPIT_TOKEN configurado via env -> exige Bearer ou X-API-Token.
    monkeypatch.setenv("YBY_COCKPIT_TOKEN", "phonebox-secret-42")
    assert (
        client_open.post(
            "/api/v1/cockpit/webhook",
            json={"action": "trigger_reindex"},
        ).status_code
        == 401
    )
    assert (
        client_open.post(
            "/api/v1/cockpit/webhook",
            json={"action": "trigger_reindex"},
            headers={"Authorization": "Bearer wrong-token"},
        ).status_code
        == 401
    )
    assert (
        client_open.post(
            "/api/v1/cockpit/webhook",
            json={"action": "trigger_reindex"},
            headers={"Authorization": "Bearer phonebox-secret-42"},
        ).status_code
        == 200
    )
    assert (
        client_open.post(
            "/api/v1/cockpit/webhook",
            json={"action": "trigger_reindex"},
            headers={"X-API-Token": "phonebox-secret-42"},
        ).status_code
        == 200
    )
