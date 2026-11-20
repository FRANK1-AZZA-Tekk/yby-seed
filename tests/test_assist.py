"""Testes do assist (mocks — sem Ollama/desktop reais)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from src.assist.config import AssistConfig, AppEntry, RoutineEntry, RoutineStep, match_routine_alias
from src.assist.reminders import ReminderStore, build_reminder
from src.assist.router import ScriptedAssistPlanner, parse_proposal
from src.assist.session import AssistSession
from src.assist.types import ToolProposal
from src.engine.providers import ProviderError
from src.main import cli
from src.memory.vault import Vault


class FakeClock:
    def __init__(self, when: datetime) -> None:
        self._when = when

    def now(self) -> datetime:
        return self._when

    def advance(self, **kwargs: int) -> None:
        from datetime import timedelta

        self._when = self._when + timedelta(**kwargs)


def _config(
    tmp_path: Path,
    *,
    apps: dict[str, tuple[str, ...]] | None = None,
    roots: list[Path] | None = None,
    routines: dict[str, RoutineEntry] | None = None,
) -> AssistConfig:
    raw_apps = apps or {"obsidian": ("obsidian",)}
    apps_norm = {
        key.casefold(): AppEntry(argv=tuple(argv)) for key, argv in raw_apps.items()
    }
    rout = routines or {
        "modo_estudo": RoutineEntry(
            aliases=("modo estudo", "ativa modo estudo", "modo_estudo"),
            steps=(
                RoutineStep("app.open", {"name": "obsidian"}),
                RoutineStep("vault.search", {"query": "embarcados", "k": 3}),
            ),
        )
    }
    return AssistConfig(
        apps=apps_norm,
        search_roots=tuple(roots or []),
        routines=rout,
        reminders_path=tmp_path / "reminders.json",
        audit_log_path=tmp_path / "audit.jsonl",
        ollama_base_url="http://127.0.0.1:9",
        ollama_timeout=1.0,
    )


def test_routine_alias_without_ollama(tmp_path: Path) -> None:
    launches: list[tuple[str, ...]] = []
    vault = Vault(tmp_path / "vault")
    vault.write_note("embarcados", "notas de sistemas embarcados ESP32")
    cfg = _config(tmp_path)
    session = AssistSession(
        config=cfg,
        planner=None,  # sem Ollama
        launcher=lambda argv: launches.append(tuple(argv)),
        vault=vault,
        confirm_fn=lambda _m: True,
    )
    assert match_routine_alias(cfg, "Ativa Modo Estudo") == "modo_estudo"
    out = session.handle("ativa modo estudo")
    assert out.result is not None and out.result.ok
    assert out.proposal is not None and out.proposal.source == "alias"
    assert launches == [("obsidian",)]
    assert "vault.search" in (out.result.data.get("ran") or [])


def test_app_not_registered_refuses(tmp_path: Path) -> None:
    launches: list[object] = []
    session = AssistSession(
        config=_config(tmp_path),
        planner=ScriptedAssistPlanner(
            [ToolProposal("app.open", {"name": "/bin/bash"}, "ollama")]
        ),
        launcher=lambda argv: launches.append(argv),
        confirm_fn=lambda _m: True,
    )
    out = session.handle("abre o bash")
    assert out.result is not None
    assert out.result.ok is False
    assert launches == []


def test_files_find_ambiguous_and_second(tmp_path: Path) -> None:
    root = tmp_path / "docs"
    root.mkdir()
    (root / "a-relatorio.txt").write_text("1", encoding="utf-8")
    (root / "b-relatorio.txt").write_text("2", encoding="utf-8")
    cfg = _config(tmp_path, roots=[root])
    session = AssistSession(
        config=cfg,
        planner=ScriptedAssistPlanner(
            [ToolProposal("files.find", {"query": "relatorio", "limit": 10}, "ollama")]
        ),
        confirm_fn=lambda _m: True,
    )
    out = session.handle("acha relatorio")
    assert out.result is not None and out.result.ok
    assert out.result.data.get("need_choice") is True
    assert len(session.file_candidates) == 2

    sel = session.handle("o segundo")
    assert sel.result is not None and sel.result.ok
    selected = sel.result.data.get("selected") or {}
    assert selected.get("name") == "b-relatorio.txt"
    assert "Não abri" in sel.result.narration


def test_files_find_blocks_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "safe"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("segredo", encoding="utf-8")
    link = root / "leak-secret.txt"
    link.symlink_to(outside)
    (root / "ok-secret-name.txt").write_text("local", encoding="utf-8")
    cfg = _config(tmp_path, roots=[root])
    session = AssistSession(
        config=cfg,
        planner=ScriptedAssistPlanner(
            [ToolProposal("files.find", {"query": "secret", "limit": 10}, "ollama")]
        ),
        confirm_fn=lambda _m: True,
    )
    out = session.handle("busca secret")
    assert out.result is not None
    names = [h["name"] for h in out.result.data.get("hits", [])]
    assert "ok-secret-name.txt" in names
    # symlink para fora não entra
    assert "leak-secret.txt" not in names


def test_vault_search_real_hits_only(tmp_path: Path) -> None:
    vault = Vault(tmp_path / "vault")
    vault.write_note("embarcados", "ESP32 firmware notes")
    session = AssistSession(
        config=_config(tmp_path),
        planner=ScriptedAssistPlanner(
            [ToolProposal("vault.search", {"query": "ESP32", "k": 3}, "ollama")]
        ),
        vault=vault,
        confirm_fn=lambda _m: True,
    )
    out = session.handle("busca no vault ESP32")
    assert out.result is not None and out.result.ok
    hits = out.result.data.get("hits") or []
    assert hits and hits[0]["name"].endswith("embarcados.md")
    assert "excerpt" not in hits[0]
    assert "sem ler o corpo" in out.result.narration.casefold() or "índice" in out.result.narration.casefold()


def test_system_status_ollama_down_separate_errors(tmp_path: Path, monkeypatch) -> None:
    from src.assist import tools as tools_mod

    monkeypatch.setattr(tools_mod, "check_ollama", lambda *_a, **_k: "indisponível")
    session = AssistSession(
        config=_config(tmp_path),
        planner=ScriptedAssistPlanner([ToolProposal("system.status", {}, "ollama")]),
        confirm_fn=lambda _m: True,
    )
    out = session.handle("status")
    assert out.result is not None
    assert out.result.data.get("ollama") == "indisponível"
    assert any("ollama" in e for e in out.result.data.get("errors", []))


def test_reminder_corrected_then_confirmed(tmp_path: Path) -> None:
    confirms: list[str] = []

    def confirm_fn(msg: str) -> bool:
        confirms.append(msg)
        # primeira (dados velhos) — se ainda pendente seria negada; fluxo: nova proposta
        return "14:00" in msg

    session = AssistSession(
        config=_config(tmp_path),
        planner=ScriptedAssistPlanner(
            [
                ToolProposal(
                    "reminder.create",
                    {"text": "estudar", "date": "2026-12-01", "time": "10:00", "tz": "UTC"},
                    "ollama",
                ),
                ToolProposal(
                    "reminder.create",
                    {"text": "estudar", "date": "2026-12-01", "time": "14:00", "tz": "UTC"},
                    "ollama",
                ),
            ]
        ),
        confirm_fn=confirm_fn,
        reminder_store=ReminderStore(tmp_path / "rem.json"),
    )
    first = session.handle("lembrete")
    assert first.result is not None and first.result.ok is False
    second = session.handle("lembrete corrigido")
    assert second.result is not None and second.result.ok is True
    assert "14:00" in second.result.narration


def test_reminder_cancel(tmp_path: Path) -> None:
    session = AssistSession(
        config=_config(tmp_path),
        planner=ScriptedAssistPlanner(
            [
                ToolProposal(
                    "reminder.create",
                    {"text": "x", "date": "2026-12-01", "time": "10:00", "tz": "UTC"},
                    "ollama",
                )
            ]
        ),
        confirm_fn=lambda _m: False,
        reminder_store=ReminderStore(tmp_path / "rem.json"),
    )
    out = session.handle("lembrete")
    assert out.result is not None and out.result.ok is False
    # cancela explícito
    session.pending_reminder = {"text": "x"}
    cancel = session.handle("cancela")
    assert session.pending_reminder is None
    assert "descartada" in cancel.user_message.casefold()


def test_routine_stops_on_step_failure(tmp_path: Path) -> None:
    cfg = _config(
        tmp_path,
        routines={
            "quebra": RoutineEntry(
                aliases=("quebra",),
                steps=(
                    RoutineStep("app.open", {"name": "obsidian"}),
                    RoutineStep("app.open", {"name": "nao_existe"}),
                    RoutineStep("chat", {"text": "nao deve"}),
                ),
            )
        },
    )
    launches: list[tuple[str, ...]] = []
    session = AssistSession(
        config=cfg,
        planner=None,
        launcher=lambda argv: launches.append(tuple(argv)),
        confirm_fn=lambda _m: True,
    )
    out = session.handle("quebra")
    assert out.result is not None
    assert out.result.ok is False
    assert out.result.data.get("ran") == ["app.open"]
    assert "nao_existe" in (out.result.data.get("failed") or "")
    assert out.result.data.get("skipped") == ["chat"]
    assert launches == [("obsidian",)]


def test_invalid_proposal_no_side_effect(tmp_path: Path) -> None:
    launches: list[object] = []

    class BadPlanner:
        def propose(self, utterance: str, *, context: str) -> ToolProposal:
            raise ValueError("json inválido")

    session = AssistSession(
        config=_config(tmp_path),
        planner=BadPlanner(),  # type: ignore[arg-type]
        launcher=lambda argv: launches.append(argv),
        confirm_fn=lambda _m: True,
    )
    out = session.handle("faz algo")
    assert out.result is None
    assert "nada executado" in out.user_message.casefold() or "inválida" in out.user_message.casefold()
    assert launches == []


def test_ollama_down_no_cloud(tmp_path: Path) -> None:
    class Down:
        def propose(self, utterance: str, *, context: str) -> ToolProposal:
            raise ProviderError("Ollama indisponível")

    session = AssistSession(
        config=_config(tmp_path),
        planner=Down(),  # type: ignore[arg-type]
        confirm_fn=lambda _m: True,
    )
    out = session.handle("abre algo aleatório")
    assert "sem fallback" in out.user_message.casefold() or "nuvem" in out.user_message.casefold()


def test_parse_proposal_and_ask_regression(monkeypatch) -> None:
    prop = parse_proposal('{"tool":"chat","args":{"text":"oi"}}')
    assert prop.tool == "chat"

    from src.engine.hybrid import EngineReply

    class _Eng:
        def reply(self, prompt: str, *, explicit_heavy: bool = False) -> EngineReply:
            return EngineReply("ok-ask", "local", "qwen2.5-coder:3b", ("local",), None)

    monkeypatch.setattr("src.main.build_engine", lambda: _Eng())
    result = CliRunner().invoke(cli, ["ask", "oi"])
    assert result.exit_code == 0
    assert "ok-ask" in result.output


def test_reminder_sessao_nao_entrega(tmp_path: Path) -> None:
    """Assist só cadastra; startup não marca nem anuncia lembretes."""

    store = ReminderStore(tmp_path / "r.json")
    rem = build_reminder(text="água", date="2020-01-01", time="00:00", tz="UTC")
    store.add(rem)
    clock = FakeClock(datetime(2020, 1, 2, tzinfo=timezone.utc))
    session = AssistSession(
        config=_config(tmp_path),
        planner=ScriptedAssistPlanner([]),
        reminder_store=store,
        clock=clock,
        confirm_fn=lambda _m: True,
    )
    assert session.startup_messages() == []
    assert store.load()[0].delivery == "scheduled"
    assert store.load()[0].delivered is False
