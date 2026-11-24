"""Testes do Sentinela (relógio e notificador substituíveis)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from click.testing import CliRunner

from src.assist.config import AssistConfig, AppEntry
from src.assist.router import ScriptedAssistPlanner
from src.assist.session import AssistSession
from src.assist.types import ToolProposal
from src.main import cli
from src.sentinel.config import QuietHours, SentinelConfig
from src.sentinel.engine import list_rules, pause_rule, resume_rule, run_once
from src.sentinel.notify import RecordingNotifier
from src.sentinel.store import load_incidents


class FakeClock:
    def __init__(self, when: datetime) -> None:
        self._when = when

    def now(self) -> datetime:
        return self._when

    def advance(self, **kwargs: float) -> None:
        self._when = self._when + timedelta(**kwargs)


def _fresh_backup(backup: Path, clock: FakeClock) -> Path:
    backup.mkdir(parents=True, exist_ok=True)
    archive = backup / "yby-vault-fresh.tar.gz"
    archive.write_bytes(b"ok")
    ts = clock.now().timestamp()
    import os

    os.utime(archive, (ts, ts))
    return backup


def _config(tmp_path: Path, clock: FakeClock | None = None, **kwargs) -> SentinelConfig:
    backup = kwargs.pop("backup_dir", None)
    if backup is None:
        clk = clock or FakeClock(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc))
        backup = _fresh_backup(tmp_path / "backups", clk)
    else:
        Path(backup).mkdir(parents=True, exist_ok=True)
    quiet = kwargs.pop("quiet_hours", None)
    state = kwargs.pop("state_dir", tmp_path / "sentinel")
    return SentinelConfig(
        state_dir=state,
        ollama_base_url="http://127.0.0.1:9",
        ollama_timeout=0.5,
        ollama_down_seconds=kwargs.pop("ollama_down_seconds", 300),
        backup_dir=Path(backup),
        backup_max_age_hours=kwargs.pop("backup_max_age_hours", 48),
        quiet_hours=quiet,
        check_interval_seconds=60,
    )


def test_ollama_uma_notificacao_por_incidente(tmp_path: Path) -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc))
    cfg = _config(tmp_path, clock=clock, ollama_down_seconds=300)
    notifier = RecordingNotifier()

    def down(_url: str, _t: float) -> str:
        return "indisponível"

    # ainda dentro da janela
    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=down)
    assert notifier.calls == []
    assert load_incidents(cfg.incidents_path) == []

    clock.advance(seconds=301)
    r2 = run_once(cfg, clock=clock, notifier=notifier, ollama_probe=down)
    assert len(notifier.calls) == 1
    assert "ollama_down" in r2.notified
    incidents = load_incidents(cfg.incidents_path)
    assert len([i for i in incidents if i.state == "active"]) == 1
    notified_at = incidents[0].notified_at
    assert notified_at is not None

    # segunda checagem na mesma falha — sem novo aviso
    clock.advance(seconds=60)
    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=down)
    assert len(notifier.calls) == 1

    # reinício do processo = reload disco — ainda um aviso
    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=down)
    assert len(notifier.calls) == 1
    assert load_incidents(cfg.incidents_path)[0].notified_at == notified_at


def test_ollama_rearme_apos_recuperacao(tmp_path: Path) -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc))
    cfg = _config(tmp_path, clock=clock, ollama_down_seconds=60)
    notifier = RecordingNotifier()
    status = {"v": "down"}

    def probe(_u: str, _t: float) -> str:
        return "ok" if status["v"] == "ok" else "indisponível"

    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=probe)  # marca fail_since
    clock.advance(seconds=61)
    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=probe)
    assert len(notifier.calls) == 1

    status["v"] = "ok"
    clock.advance(seconds=10)
    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=probe)
    active = [i for i in load_incidents(cfg.incidents_path) if i.state == "active"]
    assert active == []

    status["v"] = "down"
    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=probe)
    clock.advance(seconds=61)
    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=probe)
    assert len(notifier.calls) == 2


def test_backup_stale_vs_unverified(tmp_path: Path) -> None:
    clock = FakeClock(datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc))
    notifier = RecordingNotifier()

    empty = tmp_path / "empty_bk"
    empty.mkdir()
    cfg = _config(
        tmp_path,
        clock=clock,
        backup_dir=empty,
        state_dir=tmp_path / "sentinel_u",
        backup_max_age_hours=24,
    )
    run_once(
        cfg,
        clock=clock,
        notifier=notifier,
        ollama_probe=lambda *_a: "ok",
    )
    rules = {i.rule for i in load_incidents(cfg.incidents_path) if i.state == "active"}
    assert "vault_backup_unverified" in rules
    assert "vault_backup_stale" not in rules
    assert any("nenhum" in c[1].casefold() for c in notifier.calls)

    stale_dir = tmp_path / "stale_bk"
    stale_dir.mkdir()
    archive = stale_dir / "yby-vault-old.tar.gz"
    archive.write_bytes(b"x")
    old = (clock.now() - timedelta(hours=100)).timestamp()
    import os

    os.utime(archive, (old, old))
    cfg2 = _config(
        tmp_path,
        clock=clock,
        backup_dir=stale_dir,
        state_dir=tmp_path / "sentinel_s",
        backup_max_age_hours=48,
    )
    n2 = RecordingNotifier()
    run_once(cfg2, clock=clock, notifier=n2, ollama_probe=lambda *_a: "ok")
    rules2 = {i.rule for i in load_incidents(cfg2.incidents_path) if i.state == "active"}
    assert "vault_backup_stale" in rules2
    assert "vault_backup_unverified" not in rules2


def test_quiet_hours_pending_then_notify(tmp_path: Path) -> None:
    quiet = QuietHours(start="22:00", end="07:00")
    clock = FakeClock(datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc))
    cfg = _config(tmp_path, clock=clock, quiet_hours=quiet, ollama_down_seconds=10)
    notifier = RecordingNotifier()

    def down(_u: str, _t: float) -> str:
        return "down"

    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=down)
    clock.advance(seconds=11)
    r1 = run_once(cfg, clock=clock, notifier=notifier, ollama_probe=down)
    assert notifier.calls == []
    assert "ollama_down" in r1.pending
    inc = load_incidents(cfg.incidents_path)[0]
    assert inc.pending_notify is True
    assert inc.notified_at is None

    # ainda quiet
    clock.advance(minutes=30)
    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=down)
    assert notifier.calls == []

    # fora do silêncio
    clock._when = datetime(2026, 1, 2, 8, 0, tzinfo=timezone.utc)
    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=down)
    assert len(notifier.calls) == 1
    assert load_incidents(cfg.incidents_path)[0].notified_at is not None


def test_quiet_pending_reeval_skips_if_recovered(tmp_path: Path) -> None:
    quiet = QuietHours(start="22:00", end="07:00")
    clock = FakeClock(datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc))
    cfg = _config(tmp_path, clock=clock, quiet_hours=quiet, ollama_down_seconds=10)
    notifier = RecordingNotifier()
    status = {"v": "down"}

    def probe(_u: str, _t: float) -> str:
        return "ok" if status["v"] == "ok" else "down"

    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=probe)
    clock.advance(seconds=11)
    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=probe)
    assert notifier.calls == []

    status["v"] = "ok"
    clock._when = datetime(2026, 1, 2, 8, 0, tzinfo=timezone.utc)
    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=probe)
    assert notifier.calls == []
    assert all(i.state == "resolved" for i in load_incidents(cfg.incidents_path))


def test_desktop_indisponivel_nao_marca_entregue(tmp_path: Path) -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc))
    cfg = _config(tmp_path, clock=clock, ollama_down_seconds=5)
    notifier = RecordingNotifier(succeed=False)
    run_once(
        cfg,
        clock=clock,
        notifier=notifier,
        ollama_probe=lambda *_a: "down",
    )
    clock.advance(seconds=6)
    run_once(
        cfg,
        clock=clock,
        notifier=notifier,
        ollama_probe=lambda *_a: "down",
    )
    assert len(notifier.calls) == 1
    inc = load_incidents(cfg.incidents_path)[0]
    assert inc.notified_at is None
    assert inc.pending_notify is True


def test_pause_resume_via_engine(tmp_path: Path) -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc))
    cfg = _config(tmp_path, clock=clock, ollama_down_seconds=5)
    notifier = RecordingNotifier()
    pause_rule(cfg, "ollama_down")
    run_once(
        cfg,
        clock=clock,
        notifier=notifier,
        ollama_probe=lambda *_a: "down",
    )
    clock.advance(seconds=10)
    run_once(
        cfg,
        clock=clock,
        notifier=notifier,
        ollama_probe=lambda *_a: "down",
    )
    assert notifier.calls == []
    assert load_incidents(cfg.incidents_path) == []

    resume_rule(cfg, "ollama_down")
    run_once(
        cfg,
        clock=clock,
        notifier=notifier,
        ollama_probe=lambda *_a: "down",
    )
    clock.advance(seconds=10)
    run_once(
        cfg,
        clock=clock,
        notifier=notifier,
        ollama_probe=lambda *_a: "down",
    )
    assert len(notifier.calls) == 1


def test_assist_list_pause_resume(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "sentinel"
    state.mkdir()
    monkeypatch.setenv("YBY_SENTINEL_STATE", str(state))
    monkeypatch.setenv("YBY_BACKUP_DIR", str(tmp_path / "bk"))
    (tmp_path / "bk").mkdir()

    session = AssistSession(
        config=AssistConfig(
            apps={"x": AppEntry(argv=("true",))},
            search_roots=(),
            routines={},
            reminders_path=tmp_path / "r.json",
            audit_log_path=tmp_path / "a.jsonl",
            ollama_base_url="http://127.0.0.1:9",
            ollama_timeout=1.0,
        ),
        planner=ScriptedAssistPlanner(
            [
                ToolProposal("sentinel.rules.list", {}, "ollama"),
                ToolProposal("sentinel.rules.pause", {"rule": "ollama_down"}, "ollama"),
                ToolProposal("sentinel.rules.resume", {"rule": "ollama_down"}, "ollama"),
            ]
        ),
        confirm_fn=lambda _m: True,
    )
    listed = session.handle("lista regras")
    assert listed.result is not None and listed.result.ok
    assert "ollama_down" in listed.user_message

    paused = session.handle("pausa")
    assert paused.result is not None and paused.result.ok
    rows = list_rules(
        SentinelConfig(
            state_dir=state,
            ollama_base_url="http://127.0.0.1:9",
            ollama_timeout=1.0,
            ollama_down_seconds=300,
            backup_dir=tmp_path / "bk",
            backup_max_age_hours=48,
            quiet_hours=None,
            check_interval_seconds=60,
        )
    )
    assert next(r for r in rows if r["id"] == "ollama_down")["paused"] is True

    resumed = session.handle("retoma")
    assert resumed.result is not None and resumed.result.ok


def test_cli_sentinel_once(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "sentinel"
    monkeypatch.setenv("YBY_SENTINEL_STATE", str(state))
    monkeypatch.setenv("YBY_BACKUP_DIR", str(tmp_path / "bk"))
    (tmp_path / "bk").mkdir()
    from src.sentinel import models as m

    monkeypatch.setattr(
        "src.sentinel.engine.collect",
        lambda *_a, **_k: m.ProbeSnapshot(True, "ok", "ok", "ok", 1.0),
    )
    monkeypatch.setattr(
        "src.sentinel.engine.DesktopNotifier",
        lambda: RecordingNotifier(),
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["sentinel", "once"])
    assert result.exit_code == 0
    assert "ollama=ok" in result.output


def test_queda_apos_notify_antes_do_save_pode_reavisar(tmp_path: Path, monkeypatch) -> None:
    """Notify ok + falha em save_incidents ⇒ notified_at não persiste; nova passagem reavalia."""

    clock = FakeClock(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc))
    cfg = _config(tmp_path, clock=clock, ollama_down_seconds=5)
    notifier = RecordingNotifier()
    status = {"v": "down"}

    def probe(_u: str, _t: float) -> str:
        return "ok" if status["v"] == "ok" else "down"

    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=probe)
    clock.advance(seconds=6)

    real_save = __import__("src.sentinel.store", fromlist=["save_incidents"]).save_incidents
    calls = {"n": 0}

    def boom(path, incidents):  # noqa: ANN001
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("queda simulada após notify")
        return real_save(path, incidents)

    monkeypatch.setattr("src.sentinel.engine.save_incidents", boom)

    try:
        run_once(cfg, clock=clock, notifier=notifier, ollama_probe=probe)
    except OSError:
        pass
    assert len(notifier.calls) == 1
    # disco sem notified_at (save falhou)
    assert load_incidents(cfg.incidents_path) == [] or all(
        i.notified_at is None for i in load_incidents(cfg.incidents_path)
    )

    # reinício com falha ainda ativa → segundo aviso
    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=probe)
    assert len(notifier.calls) == 2
    assert load_incidents(cfg.incidents_path)[0].notified_at is not None


def test_queda_apos_notify_nao_envia_alerta_velho_se_recuperou(
    tmp_path: Path, monkeypatch
) -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc))
    cfg = _config(tmp_path, clock=clock, ollama_down_seconds=5)
    notifier = RecordingNotifier()
    status = {"v": "down"}

    def probe(_u: str, _t: float) -> str:
        return "ok" if status["v"] == "ok" else "down"

    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=probe)
    clock.advance(seconds=6)

    def boom(_path, _incidents):  # noqa: ANN001
        raise OSError("queda simulada")

    monkeypatch.setattr("src.sentinel.engine.save_incidents", boom)
    try:
        run_once(cfg, clock=clock, notifier=notifier, ollama_probe=probe)
    except OSError:
        pass
    assert len(notifier.calls) == 1

    status["v"] = "ok"
    monkeypatch.setattr(
        "src.sentinel.engine.save_incidents",
        __import__("src.sentinel.store", fromlist=["save_incidents"]).save_incidents,
    )
    # runtime ainda tem fail_since do tick anterior; coleta mostra ok → resolve / não reenvia
    clock.advance(seconds=1)
    # recria runtime limpo após crash: simula processo novo com disco vazio de incidents
    # e runtime que ainda pode existir — se incidents vazios e ollama ok, zero avisos
    run_once(cfg, clock=clock, notifier=notifier, ollama_probe=probe)
    assert len(notifier.calls) == 1
