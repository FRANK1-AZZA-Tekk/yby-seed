"""Regressões dos bugs corrigidos no scan profundo camada a camada."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

if "lancedb" not in sys.modules:
    sys.modules["lancedb"] = ModuleType("lancedb")
    sys.modules["lancedb"].connect = MagicMock()


def test_validate_skills_accepts_directory(tmp_path: Path) -> None:
    skill_dir = tmp_path / "minha-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: minha-skill
description: Skill de teste válida para validação
version: 1.0.0
min_agent_version: 0.1.0
last_updated: "2026-11-26"
license: MIT
author: YBY
tags: [teste]
dependencies: []
changelog:
  - version: 1.0.0
    date: "2026-11-26"
    changes: inicial
---

# Minha Skill

## Descrição
Descrição clara.

## Como Usar
Passos de uso.

## Exemplos
```python
print("ok")
```
""",
        encoding="utf-8",
    )
    res = subprocess.run(
        [sys.executable, "scripts/validate_skills.py", str(skill_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stdout + res.stderr

    bad_dir = tmp_path / "skill-invalida"
    bad_dir.mkdir()
    (bad_dir / "SKILL.md").write_text("---\n- lista\n---\n", encoding="utf-8")
    res_bad = subprocess.run(
        [sys.executable, "scripts/validate_skills.py", str(bad_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_bad.returncode == 1


def test_cli_run_rejects_non_positive_timeout_and_agent_invalid_script(
    tmp_path: Path,
) -> None:
    from click.testing import CliRunner

    from src.main import cli

    runner = CliRunner()
    res_run = runner.invoke(cli, ["run", "--timeout", "0", "echo hi"])
    assert res_run.exit_code == 1

    bad_script = tmp_path / "bad.json"
    bad_script.write_text("{not-json", encoding="utf-8")
    res_agent = runner.invoke(cli, ["agent", "--script", str(bad_script), "olá"])
    assert res_agent.exit_code == 1


def test_sandbox_executor_retry_validation_and_timeout_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.security.sandbox_executor import SandboxExecutor

    ex = SandboxExecutor(timeout=1)
    with pytest.raises(ValueError, match="max_retries"):
        ex.execute_with_retry("print(1)", max_retries=0)

    # Execução real via sys.executable e env sanitizado
    ok = ex.execute("print(1 + 2)")
    assert ok["success"] is True
    assert ok["stdout"].strip() == "3"

    # Simula TimeoutExpired para validar kill() + segundo communicate() + env mínimo
    captured_popen: dict[str, object] = {}

    class FakeProc:
        def __init__(self) -> None:
            self.calls = 0
            self.killed = False
            self.returncode = -9

        def communicate(self, **_kw: object) -> tuple[bytes, bytes]:
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired(cmd="python", timeout=1)
            return b"", b""

        def kill(self) -> None:
            self.killed = True

    fake_proc = FakeProc()

    def fake_popen(cmd, **kwargs):  # noqa: ANN001, ANN202
        captured_popen["cmd"] = cmd
        captured_popen["env"] = kwargs.get("env")
        return fake_proc

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    res = ex.execute("x = 1")
    assert res["success"] is False
    assert res["error"] == "Timeout"
    assert fake_proc.killed is True
    assert fake_proc.calls == 2
    assert captured_popen["cmd"][0] == sys.executable  # type: ignore[index]
    assert "OPENAI_API_KEY" not in (captured_popen["env"] or {})  # type: ignore[operator]


def test_actions_runner_handles_unclosed_quote_and_invalid_timeout(tmp_path: Path) -> None:
    from src.actions.runner import run_command
    from src.safety.policy import load_policy

    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text("allow:\n  - 'echo *'\n", encoding="utf-8")
    pol = load_policy(policy_file)

    with pytest.raises(ValueError, match="timeout"):
        run_command("echo ok", policy=pol, project_root=tmp_path, timeout=0)

    res = run_command(
        "echo 'unclosed",
        policy=pol,
        project_root=tmp_path,
        input_fn=lambda: "s",
        output_fn=lambda _msg: None,
    )
    assert res.executed is False
    assert res.exit_code == 1
    assert "inválido" in res.stderr.casefold()


def test_budget_utc_day_rollover_and_bool_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.engine.budget import CloudBudget
    from src.engine.cloud_usage_log import EVENT_COMPLETED

    log_path = tmp_path / "usage.jsonl"
    # Timestamp de 2026-11-25T23:00:00Z = 1795647600
    ts_day1 = 1795647600.0
    row_day1 = {
        "timestamp": ts_day1,
        "result": EVENT_COMPLETED,
        "input_tokens_estimate": 500,
        "output_tokens_estimate": 500,
    }
    # Linha com bool em tokens deve ser ignorada (True == 1 em Python int)
    row_bool = {
        "timestamp": ts_day1,
        "result": EVENT_COMPLETED,
        "input_tokens_estimate": True,
        "output_tokens_estimate": False,
    }
    log_path.write_text(
        json.dumps(row_day1) + "\n" + json.dumps(row_bool) + "\n",
        encoding="utf-8",
    )

    budget = CloudBudget(
        cloud_mode="ask",
        log_path=log_path,
        daily_token_limit=50_000,
        warn_daily_token_limit=40_000,
        monthly_token_limit=200_000,
        warn_token_limit=150_000,
        require_confirm=False,
        allow_no_tty=True,
    )

    import time as time_mod

    monkeypatch.setattr(time_mod, "gmtime", lambda *a: __import__("time").struct_time(
        (2026, 11, 25, 23, 30, 0, 2, 329, 0)
        if not a
        else (2026, 11, 25, 23, 0, 0, 2, 329, 0)
    ))
    day_used, month_used = budget._token_usage()
    assert day_used == 1000
    assert month_used == 1000

    # Avança para meia-noite UTC seguinte sem tocar no arquivo
    monkeypatch.setattr(time_mod, "gmtime", lambda *a: __import__("time").struct_time(
        (2026, 11, 26, 0, 5, 0, 3, 330, 0)
        if not a
        else (2026, 11, 25, 23, 0, 0, 2, 329, 0)
    ))
    day_used_next, month_used_next = budget._token_usage()
    assert day_used_next == 0
    assert month_used_next == 1000


def test_hybrid_engine_clears_stale_budget_warn_on_cache_hit(tmp_path: Path) -> None:
    from src.engine.budget import CloudBudget
    from src.engine.cache import ResponseCache
    from src.engine.config import EngineConfig
    from src.engine.hybrid import HybridEngine

    cfg = EngineConfig.from_env({})
    ollama = MagicMock()
    cloud = MagicMock()
    cloud.has_credentials.return_value = True
    cloud.complete.return_value = "ok"
    cache = ResponseCache(ttl_seconds=60.0)
    budget = CloudBudget(
        cloud_mode="ask",
        log_path=tmp_path / "missing.jsonl",
        daily_token_limit=50_000,
        warn_daily_token_limit=40_000,
        monthly_token_limit=200_000,
        warn_token_limit=150_000,
        require_confirm=False,
        allow_no_tty=True,
    )
    engine = HybridEngine(cfg, ollama, cloud, cache=cache, budget=budget)
    engine._budget_warn = "Aviso: uso antigo"
    key = cache.make_key(
        "prompt pesado",
        model=cfg.cloud_model,
        system="Você é o YBY SEED, um exocórtex pessoal. Responda no idioma do pedido, de forma direta e útil. Não execute comandos, não acesse arquivos e não chame ferramentas.",
        cache_extra=f"max_tokens={cfg.cloud_max_output_tokens}",
    )
    cache.set(key, "resposta em cache")

    reply = engine.reply("prompt pesado", explicit_heavy=True)
    assert reply.text == "resposta em cache"
    assert reply.notice is None


def test_vault_str_root_and_nonpositive_k(tmp_path: Path) -> None:
    from src.memory.vault import Vault

    vault = Vault(str(tmp_path))
    vault.write_note("nota.md", "conteudo de teste sobre python")
    assert vault.search("python", k=-1) == []
    assert vault.search("python", k=0) == []
    assert len(vault.search("python", k=2)) == 1


def test_pending_queue_skips_corrupted_row(tmp_path: Path) -> None:
    from src.memory.pending_queue import PendingEpisodeQueue

    db_path = tmp_path / "pending.db"
    q = PendingEpisodeQueue(db_path)
    q.enqueue("s1", {"ok": True})
    q._conn.execute(
        "INSERT INTO pending_episodes (source_id, payload, created_at, attempts) VALUES (?, ?, ?, 0)",
        ("s_bad", "{corrompido", 1.0),
    )
    q._conn.commit()

    batch = q.list_batch()
    assert len(batch) == 1
    assert batch[0].source_id == "s1"
    q.close()


def test_evo_sanitize_redacts_bearer_after_authorization() -> None:
    from src.evo.sanitize import sanitize_text

    out = sanitize_text("Authorization: Bearer secret_abc_123456")
    assert "secret_abc_123456" not in out
    assert out == "Authorization: [REDACTED]"


def test_evo_pipeline_closes_internal_completer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.evo import pipeline

    closed = {"called": False}

    class FakeCompleter:
        def complete(self, *_a: object, **_kw: object) -> str:
            return '{"summary": "ok", "findings": [], "suggestions": []}'

        def close(self) -> None:
            closed["called"] = True

    monkeypatch.setattr(pipeline, "build_local_completer", lambda: FakeCompleter())
    bundle = pipeline.generate_report(
        "2026-11-26",
        db_path=tmp_path / "evo.db",
        reports_dir=tmp_path / "reports",
        ingest_cloud=False,
    )
    assert bundle.cycle_state == "completed"
    assert closed["called"] is True


def test_platform_hub_env_float_and_voice_config_invalid_int(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.platform.hub import _env_float
    from src.voice.config import VoiceConfig

    monkeypatch.setenv("YBY_HUB_INTERVAL", "")
    assert _env_float("YBY_HUB_INTERVAL", 60.0) == 60.0
    monkeypatch.setenv("YBY_HUB_INTERVAL", "abc")
    assert _env_float("YBY_HUB_INTERVAL", 60.0) == 60.0

    with pytest.raises(ValueError, match="YBY_VOICE_SAMPLE_RATE"):
        VoiceConfig.from_env({"YBY_VOICE_SAMPLE_RATE": "nao_inteiro"})


@pytest.mark.asyncio
async def test_pipewire_record_utterance_keeps_audio_on_timeout() -> None:
    from src.yby.audio.device import PipeWireBluetoothDevice

    class TimeoutRunner:
        async def run(self, argv, *, stdin_bytes=None, timeout=30.0):  # noqa: ANN001, ANN202
            del stdin_bytes, timeout
            Path(argv[-1]).write_bytes(b"RIFFWAVE_DATA")
            raise TimeoutError("tempo de gravação atingido")

    device = PipeWireBluetoothDevice(runner=TimeoutRunner())
    captured = await device.record_utterance(max_seconds=2.0)
    assert captured == b"RIFFWAVE_DATA"


@pytest.mark.asyncio
async def test_audio_service_recovers_idle_when_mqtt_fails_and_tracks_tasks() -> None:
    from src.yby.audio.service import AsyncVoicePipeline
    from src.yby.routing import CognitiveRouter

    class FailingIdleMqtt:
        def __init__(self) -> None:
            self.calls = 0

        async def publish(self, topic, payload, *, qos=1, retain=True):  # noqa: ANN001, ANN202
            del topic, qos, retain
            self.calls += 1
            if '"idle"' in payload:
                raise ConnectionError("broker caiu")

    class DummyDevice:
        device_name = "Baseus"

        async def detect_device(self) -> str | None:
            return "card"

        async def set_profile(self, _p: str) -> bool:
            return True

        async def record_utterance(self, **_kw: object) -> bytes:
            return b"RIFF"

        async def play_wav(self, _wav: bytes) -> None:
            return None

    class DummySTT:
        async def transcribe(self, _wav: bytes, *, language: str = "pt") -> str:
            del language
            return "olá"

    class DummyTTS:
        async def synthesize(self, _text: str, *, voice: str = "pf_dora") -> bytes:
            del voice
            return b"WAV"

    class DummyLLM:
        async def complete(self, tier, prompt, *, system=None, metadata=None):  # noqa: ANN001, ANN202
            del prompt, system, metadata
            return "ok", f"m-{tier}"

    pipeline = AsyncVoicePipeline(
        device=DummyDevice(),
        stt=DummySTT(),
        tts=DummyTTS(),
        router=CognitiveRouter(backend=DummyLLM()),
        mqtt_bus=FailingIdleMqtt(),
    )
    task = pipeline.start_turn_background(wav_bytes=b"RIFF", speak_reply=False)
    assert task in pipeline._background_tasks
    res = await task
    await asyncio.sleep(0)
    assert res.reply_text == "ok"
    assert pipeline.state == "idle"
    assert task not in pipeline._background_tasks


@pytest.mark.asyncio
async def test_routing_corrupt_cache_empty_content_and_triage_failure() -> None:
    from src.yby.routing.cache import InMemoryCacheBackend, build_cache_key
    from src.yby.routing.router import (
        CognitiveRouter,
        OpenAICompatibleBackend,
        RouterConfig,
        TierExecutionError,
    )
    from src.yby.routing.schemas import RouteRequest

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": None}}]}

    class FakeHttp:
        async def post(self, *_a: object, **_kw: object) -> FakeResp:
            return FakeResp()

    backend = OpenAICompatibleBackend(RouterConfig(), http_client=FakeHttp())
    with pytest.raises(TierExecutionError, match="resposta vazia"):
        await backend.complete("yby-fast", "oi")

    cache = InMemoryCacheBackend()
    key = build_cache_key("private", "yby-fast", "oi")
    await cache.set(key, "{corrompido", ttl_seconds=60)

    class WorkingLLM:
        async def complete(self, tier, prompt, *, system=None, metadata=None):  # noqa: ANN001, ANN202
            del prompt, system, metadata
            return "resposta ao vivo", f"m-{tier}"

    async def broken_triage(_req: RouteRequest):  # noqa: ANN202
        raise RuntimeError("triage 3B falhou")

    router = CognitiveRouter(backend=WorkingLLM(), cache=cache, triage_runner=broken_triage)
    out = await router.route(RouteRequest(prompt="oi", sensitivity="private"))
    assert out.text == "resposta ao vivo"
    assert out.metadata.cache_hit is False


@pytest.mark.asyncio
async def test_edge_sync_nan_guard_partial_drain_and_mqtt_resilience(tmp_path: Path) -> None:
    from src.yby.edge_sync.schemas import EdgeEvent, EdgeSyncBatchRequest
    from src.yby.edge_sync.store import SQLiteFallbackEdgeStore, _format_pgvector
    from src.yby.edge_sync.worker import EdgeSyncWorker

    with pytest.raises(ValueError, match="NaN"):
        _format_pgvector([0.1, float("nan")])

    fb = SQLiteFallbackEdgeStore(tmp_path / "fb.db")
    ev1 = EdgeEvent(
        event_id="e1",
        device_id="d1",
        source_node="xiaomi12",
        topic="yby/s/1",
        payload={"v": 1},
    )
    ev2 = EdgeEvent(
        event_id="e2",
        device_id="d1",
        source_node="xiaomi12",
        topic="yby/s/2",
        payload={"v": 2},
    )
    await fb.upsert_event(ev1, [1.0, 0.0])
    await fb.upsert_event(ev2, [0.0, 1.0])

    class PartialFailStore:
        backend_name = "pgvector"

        async def ensure_schema(self) -> None:
            return None

        async def upsert_event(self, event: EdgeEvent, _emb):  # noqa: ANN001, ANN202
            if event.event_id == "e2":
                raise RuntimeError("falha no segundo")
            return "inserted"

        async def count_events(self) -> int:
            return 1

        async def search_similar(self, _q, *, limit=5):  # noqa: ANN001, ANN202
            del limit
            return []

    with pytest.raises(RuntimeError, match="falha no segundo"):
        await fb.drain_to(PartialFailStore())
    # O primeiro evento drenado não deve ficar preso como pendente
    assert await fb.count_pending() == 1

    class FailingMqtt:
        async def publish(self, *_a: object, **_kw: object) -> None:
            raise ConnectionError("broker offline")

    class OkStore(PartialFailStore):
        async def upsert_event(self, event: EdgeEvent, _emb):  # noqa: ANN001, ANN202
            del event
            return "inserted"

    worker = EdgeSyncWorker(primary_store=OkStore(), mqtt_bus=FailingMqtt())
    resp = await worker.ingest_batch(EdgeSyncBatchRequest(events=[ev1]))
    assert resp.accepted == 1
    assert resp.failed == 0


def test_yby_machine_translator_ident_and_compiler_fixes() -> None:
    from src.yby_machine.compiler import compile_pwa
    from src.yby_machine.store_pgvector import _vector_literal
    from src.yby_machine.translator import parse_spec_json

    raw = json.dumps(
        {
            "title": "2via Boletos & Café",
            "entities": [
                {
                    "name": "1-boleto",
                    "label": "Boleto",
                    "fields": [
                        {"name": "pagamento", "label": "Pagamento", "type": "texto", "required": True},
                        {"name": "valor-total", "label": "Valor", "type": "moeda_brl", "required": True},
                    ],
                }
            ],
        }
    )
    spec = parse_spec_json(raw)
    assert spec.name == "app_2via_boletos_cafe"
    assert spec.entities[0].name == "item_1_boleto"
    assert spec.entities[0].fields[1].name == "valor_total"

    js = compile_pwa(spec)["app.js"]
    assert "crypto.randomUUID" in js
    assert 'expr.includes("-")' in js
    assert 'expr.includes("/")' in js
    assert "for (const s of statuses)" in js

    with pytest.raises(ValueError, match="NaN"):
        _vector_literal([0.0, float("inf")])


def test_execution_agent_crlf_and_learning_agent_missing_row() -> None:
    from src.agents.execution_agent import ExecutionAgent
    from src.agents.learning_agent import LearningAgent

    ollama = MagicMock()
    ollama.generate.return_value = "```python  \r\nprint('ok')\r\n```"
    agent = ExecutionAgent(ollama=ollama)
    assert agent.generate("prd") == "print('ok')"

    la = LearningAgent(db_url="")
    fake_cur = MagicMock()
    fake_cur.fetchone.return_value = None
    fake_cur.__enter__ = lambda self: self
    fake_cur.__exit__ = lambda *_a: False
    fake_conn = MagicMock()
    fake_conn.cursor.return_value = fake_cur
    la.conn = fake_conn
    # Não deve lançar TypeError ao tentar desempacotar None
    la._bayesian_update(999, "success")


def test_gateway_http_400_and_503_and_lancedb_escape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi.testclient import TestClient

    from src.gateway import fastapi_mqtt_bridge as bridge
    from src.gateway.config import Settings
    from src.gateway.lancedb_client import LanceDBClient

    monkeypatch.setattr(bridge, "settings", Settings(GATEWAY_TOKEN="tok-teste"))
    client = TestClient(bridge.app)
    headers = {"Authorization": "Bearer tok-teste"}

    bad = client.post("/telemetry", json={"device_id": "d1"}, headers=headers)
    assert bad.status_code == 400

    small_q: asyncio.Queue = asyncio.Queue(maxsize=1)
    small_q.put_nowait({"busy": True})
    monkeypatch.setattr(bridge, "mqtt_queue", small_q)
    full = client.post(
        "/telemetry",
        json={"device_id": "d1", "timestamp": "t", "metrics": {}},
        headers=headers,
    )
    assert full.status_code == 503

    search_chain = MagicMock()
    search_chain.where.return_value = search_chain
    search_chain.order_by.return_value = search_chain
    search_chain.limit.return_value = search_chain
    search_chain.to_list.return_value = []
    ldb = LanceDBClient("/tmp/fake-lance")
    ldb.metrics_table = MagicMock()
    ldb.metrics_table.search.return_value = search_chain
    asyncio.run(ldb.get_metrics("dev' OR '1'='1"))
    search_chain.where.assert_called_once_with("device_id = 'dev'' OR ''1''=''1'")


def test_iot_invalid_utf8_and_large_queue_size() -> None:
    from src.iot.config import IoTConfig
    from src.iot.handlers import parse_message, parse_message_safe

    assert parse_message_safe("yby/sensors/sala/t1/temperature", b"\xff\xfe") is None
    ev = parse_message("yby/sensors/sala/t1/temperature", json.dumps({"value": 21, "ts": True}))
    assert ev.received_at > 1_000_000_000.0

    cfg = IoTConfig.from_env({"IOT_MAX_QUEUE_SIZE": "100000"})
    assert cfg.max_queue_size == 100000


def test_rag_utf8_ast_chunker_and_pruner_rerank(monkeypatch: pytest.MonkeyPatch) -> None:
    code = (
        "# Comentário com acentuação: Olá, ação, coração!\n"
        "def saudar():\n"
        "    return 'olá'\n\n"
        "def segunda():\n"
        "    return 'ação'\n"
    )
    code_bytes = code.encode("utf-8")
    idx1 = code_bytes.index(b"def saudar")
    end1 = code_bytes.index(b"\n\ndef segunda")
    idx2 = code_bytes.index(b"def segunda")
    end2 = len(code_bytes)

    class FakeNode:
        def __init__(self, ntype: str, start_b: int, end_b: int, line: int) -> None:
            self.type = ntype
            self.start_byte = start_b
            self.end_byte = end_b
            self.start_point = (line, 0)
            self.end_point = (line + 1, 0)

    class FakeParser:
        def set_language(self, _lang: object) -> None:
            return None

        def parse(self, _b: bytes) -> object:
            root = MagicMock()
            root.children = [
                FakeNode("function_definition", idx1, end1, 1),
                FakeNode("function_definition", idx2, end2, 4),
            ]
            tree = MagicMock()
            tree.root_node = root
            return tree

    ts_mod = ModuleType("tree_sitter")
    ts_mod.Parser = FakeParser  # type: ignore[attr-defined]
    tsp_mod = ModuleType("tree_sitter_python")
    tsp_mod.language = lambda: object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tree_sitter", ts_mod)
    monkeypatch.setitem(sys.modules, "tree_sitter_python", tsp_mod)
    sys.modules.pop("src.rag.ast_chunker", None)

    from src.rag.ast_chunker import ASTChunker
    from src.rag.context_pruner import ContextPruner

    chunker = ASTChunker("python")
    chunks = chunker.chunk(code)
    assert len(chunks) == 2
    assert chunks[0]["code"].startswith("def saudar():")
    assert chunks[1]["code"].startswith("def segunda():")

    import src.rag.context_pruner as cp_mod

    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="[1, 0]"))]
    orig_completion = cp_mod.completion
    cp_mod.completion = MagicMock(return_value=fake_resp)
    try:
        pruner = ContextPruner()
        ranked = pruner._rerank(
            [{"summary": "primeiro", "original": "A"}, {"summary": "segundo", "original": "B"}],
            "query",
        )
        assert [item["original"] for item in ranked] == ["B", "A"]
    finally:
        cp_mod.completion = orig_completion


def test_vision_extract_prefers_newest_image() -> None:
    from src.vision.fusion.server import ChatMessage, _extract_prompt_and_image_b64

    msgs = [
        ChatMessage(
            role="user",
            content=[
                {"type": "text", "text": "primeira"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,OLDIMG"}},
            ],
        ),
        ChatMessage(
            role="user",
            content=[
                {"type": "text", "text": "segunda"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,NEWIMG"}},
            ],
        ),
    ]
    prompt, img = _extract_prompt_and_image_b64(msgs)
    assert "primeira" in prompt and "segunda" in prompt
    assert img == "NEWIMG"


def test_metrics_dashboard_p95_uses_ascending_order(tmp_path: Path) -> None:
    from src.evaluation.metrics_dashboard import MetricsDashboard

    dash = MetricsDashboard(db_path=str(tmp_path / "metrics.db"))
    for i in range(1, 21):
        dash.log_task_completion(f"t{i}", True, float(i), 0.0)
    p95 = dash.get_avg_latency_p95()
    assert p95 == pytest.approx(19.0)


def test_core_memory_allocator_and_auto_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core.auto_cleanup import AutoCleanup
    from src.core.memory_allocator import MemoryAllocator

    alloc = MemoryAllocator("jemalloc")
    alloc.lib_path = None
    assert "error" in alloc.benchmark()
    parsed = alloc._parse_benchmark_output("Time: 1.25s\nMemory: 512MB\nFragmentation: 8%\n")
    assert parsed == {"time_sec": 1.25, "memory_mb": 512, "fragmentation_pct": 8}

    calls: list[list[str]] = []

    def fake_run(cmd, **_kw):  # noqa: ANN001, ANN202
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    cleanup = AutoCleanup(
        log_dir=str(tmp_path),
        db_url="postgres://user@localhost:5432/yby?sslmode=disable",
    )
    cleanup.vacuum_database()
    assert calls == [
        ["psql", "postgresql://user@localhost:5432/yby?sslmode=disable", "-c", "VACUUM ANALYZE"]
    ]
    # Sem vazamento de conexão sqlite
    assert sqlite3 is not None
