"""T10 / S4: authz de vault antes do egresso (#42)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.engine.budget import CloudBudget
from src.engine.cloud_usage_log import EVENT_BLOCKED_AUTHZ, CloudUsageLog
from src.engine.config import EngineConfig
from src.engine.hybrid import HybridEngine
from src.engine.routing import DEFAULT_HEAVY_PHRASES
from src.security.cloud_authz import (
    CODE_BLOCKED_AUTHZ,
    check_cloud_prompt,
    vault_allowed,
    vault_root,
)


def _config() -> EngineConfig:
    return EngineConfig(
        ollama_base_url="http://ollama.test",
        local_model="qwen2.5-coder:3b",
        cloud_base_url="https://openrouter.ai/api/v1",
        cloud_model="openrouter/free",
        cloud_api_key="test-key",
        cloud_fallback_base_url="https://api.x.ai/v1",
        cloud_fallback_model="grok-4.7",
        cloud_fallback_api_key="",
        heavy_min_chars=1200,
        heavy_min_lines=25,
        heavy_min_questions=3,
        heavy_phrases=DEFAULT_HEAVY_PHRASES,
        ollama_timeout=5.0,
        cloud_timeout=5.0,
        cache_ttl_seconds=0.0,
        cloud_max_chars=12000,
    )


class FakeOllama:
    def complete(self, prompt: str, *, model: str, system: str) -> str:
        return "local-ok"


class CapturingCloud:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def has_credentials(self) -> bool:
        return True

    def complete(self, prompt: str, *, model: str, system: str) -> str:
        self.calls.append(prompt)
        return "ok-from-cloud"


def test_vault_allowed_defaults_off() -> None:
    assert vault_allowed({}) is False
    assert vault_allowed({"YBY_CLOUD_ALLOW_VAULT": "0"}) is False
    assert vault_allowed({"YBY_CLOUD_ALLOW_VAULT": "1"}) is True


def test_check_allows_when_no_vault_path() -> None:
    decision = check_cloud_prompt(
        "pensa mais: leia /tmp/nota.md",
        environ={"YBY_VAULT_PATH": "", "YBY_CLOUD_ALLOW_VAULT": "0"},
    )
    assert decision.allowed is True


def test_check_blocks_vault_path_without_allow(tmp_path: Path) -> None:
    vault = tmp_path / "obsidian"
    vault.mkdir()
    note = vault / "diario.md"
    note.write_text("segredo", encoding="utf-8")
    env = {
        "YBY_VAULT_PATH": str(vault),
        "YBY_CLOUD_ALLOW_VAULT": "0",
    }
    assert vault_root(env) == vault.resolve()
    decision = check_cloud_prompt(
        f"pensa mais: resuma {note.resolve()}",
        environ=env,
    )
    assert decision.allowed is False
    assert decision.code == CODE_BLOCKED_AUTHZ
    assert "ALLOW_VAULT" in decision.reason


def test_check_allows_vault_path_with_grant(tmp_path: Path) -> None:
    vault = tmp_path / "obsidian"
    vault.mkdir()
    path = str((vault / "a.md").resolve())
    decision = check_cloud_prompt(
        f"pensa mais: {path}",
        environ={
            "YBY_VAULT_PATH": str(vault),
            "YBY_CLOUD_ALLOW_VAULT": "1",
        },
    )
    assert decision.allowed is True


def test_hybrid_t10_blocks_vault_without_authz(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "privado.md"
    note.write_text("dado sensivel do vault", encoding="utf-8")
    monkeypatch.setenv("YBY_VAULT_PATH", str(vault))
    monkeypatch.setenv("YBY_CLOUD_ALLOW_VAULT", "0")
    monkeypatch.delenv("YBY_CLOUD_BUDGET_EXCEPTION", raising=False)

    with TemporaryDirectory() as td:
        log_path = Path(td) / "cloud.jsonl"
        cloud = CapturingCloud()
        engine = HybridEngine(
            _config(),
            FakeOllama(),
            cloud,
            cloud_log=CloudUsageLog(log_path),
            budget=CloudBudget.from_env(
                {
                    "YBY_CLOUD_DB_PATH": "off",
                    "YBY_CLOUD_MODE": "ask",
                    "YBY_CLOUD_REQUIRE_CONFIRM": "0",
                    "YBY_CLOUD_LOG_PATH": str(log_path),
                }
            ),
            confirm_fn=lambda _m: True,
            has_tty_fn=lambda: True,
        )
        prompt = f"pensa mais: leia o vault em {note.resolve()}"
        reply = engine.reply(prompt)
        assert cloud.calls == []
        assert EVENT_BLOCKED_AUTHZ in log_path.read_text(encoding="utf-8")
        # Fallback local (D12 pattern) — nuvem não foi chamada.
        assert reply.provider in {"local", "none"}
        assert "vault" in (reply.notice or "").casefold() or "allow_vault" in (
            reply.notice or ""
        ).casefold()


def test_hybrid_t10_allows_with_vault_grant(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "ok.md"
    note.write_text("publico", encoding="utf-8")
    monkeypatch.setenv("YBY_VAULT_PATH", str(vault))
    monkeypatch.setenv("YBY_CLOUD_ALLOW_VAULT", "1")

    with TemporaryDirectory() as td:
        log_path = Path(td) / "cloud.jsonl"
        cloud = CapturingCloud()
        engine = HybridEngine(
            _config(),
            FakeOllama(),
            cloud,
            cloud_log=CloudUsageLog(log_path),
            budget=CloudBudget.from_env(
                {
                    "YBY_CLOUD_DB_PATH": "off",
                    "YBY_CLOUD_MODE": "ask",
                    "YBY_CLOUD_REQUIRE_CONFIRM": "0",
                    "YBY_CLOUD_LOG_PATH": str(log_path),
                }
            ),
            confirm_fn=lambda _m: True,
            has_tty_fn=lambda: True,
        )
        prompt = f"pensa mais: contexto {note.resolve()}"
        reply = engine.reply(prompt)
        assert reply.provider == "cloud"
        assert len(cloud.calls) == 1
        lines = [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert not any(row.get("result") == EVENT_BLOCKED_AUTHZ for row in lines)
