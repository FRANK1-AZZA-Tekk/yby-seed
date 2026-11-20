"""Entrega em segundo plano dos lembretes (relógio e notificador injetáveis)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from click.testing import CliRunner

from src.assist.config import AssistConfig
from src.assist.delivery import deliver_due
from src.assist.reminders import ReminderStore, build_reminder, effective_delivery
from src.assist.router import ScriptedAssistPlanner
from src.assist.session import AssistSession
from src.main import cli
from src.painel.readers import read_reminders
from src.sentinel.config import QuietHours
from src.sentinel.notify import RecordingNotifier


class FakeClock:
    def __init__(self, when: datetime) -> None:
        self._when = when

    def now(self) -> datetime:
        return self._when

    def advance(self, **kwargs: float) -> None:
        self._when = self._when + timedelta(**kwargs)


def _cfg(tmp_path: Path) -> AssistConfig:
    return AssistConfig(
        apps={},
        search_roots=(),
        routines={},
        reminders_path=tmp_path / "reminders.json",
        audit_log_path=tmp_path / "audit.jsonl",
        ollama_base_url="http://127.0.0.1:9",
        ollama_timeout=1.0,
    )


def test_sessao_nao_entrega(tmp_path: Path) -> None:
    store = ReminderStore(tmp_path / "r.json")
    rem = build_reminder(text="água", date="2020-01-01", time="00:00", tz="UTC")
    store.add(rem)
    clock = FakeClock(datetime(2020, 1, 2, tzinfo=timezone.utc))
    session = AssistSession(
        config=_cfg(tmp_path),
        planner=ScriptedAssistPlanner([]),
        reminder_store=store,
        clock=clock,
        confirm_fn=lambda _m: True,
    )
    assert session.startup_messages() == []
    assert store.load()[0].delivery == "scheduled"
    assert effective_delivery(store.load()[0], clock.now()) == "pending"


def test_cli_fechada_reminders_once_notifica(tmp_path: Path) -> None:
    store = ReminderStore(tmp_path / "r.json")
    rem = build_reminder(text="água", date="2020-01-01", time="00:00", tz="UTC")
    store.add(rem)
    clock = FakeClock(datetime(2020, 1, 2, tzinfo=timezone.utc))
    notifier = RecordingNotifier()
    result = deliver_due(store, clock=clock, notifier=notifier)
    assert rem.id in result.notified
    assert len(notifier.calls) == 1
    assert store.load()[0].delivery == "delivered"
    # segunda passagem não repete
    deliver_due(store, clock=clock, notifier=notifier)
    assert len(notifier.calls) == 1


def test_terminal_ocioso_entrega_nao_le_stdin(tmp_path: Path, monkeypatch) -> None:
    store = ReminderStore(tmp_path / "r.json")
    rem = build_reminder(text="x", date="2020-01-01", time="00:00", tz="UTC")
    store.add(rem)
    clock = FakeClock(datetime(2020, 1, 2, tzinfo=timezone.utc))
    notifier = RecordingNotifier()

    def boom(_prompt: str = "") -> str:
        raise AssertionError("entrega não deve ler stdin")

    monkeypatch.setattr("builtins.input", boom)
    deliver_due(store, clock=clock, notifier=notifier)
    assert store.load()[0].delivered is True


def test_desktop_falha_fica_pending(tmp_path: Path) -> None:
    store = ReminderStore(tmp_path / "r.json")
    rem = build_reminder(text="x", date="2020-01-01", time="00:00", tz="UTC")
    store.add(rem)
    clock = FakeClock(datetime(2020, 1, 2, tzinfo=timezone.utc))
    notifier = RecordingNotifier(succeed=False)
    result = deliver_due(store, clock=clock, notifier=notifier)
    assert rem.id in result.pending
    assert store.load()[0].delivery == "pending"
    assert store.load()[0].delivered is False
    # reinício tenta de novo
    notifier2 = RecordingNotifier(succeed=True)
    deliver_due(store, clock=clock, notifier=notifier2)
    assert len(notifier2.calls) == 1
    assert store.load()[0].delivery == "delivered"


def test_quiet_hours_depois_avisa(tmp_path: Path) -> None:
    store = ReminderStore(tmp_path / "r.json")
    rem = build_reminder(text="noite", date="2020-01-01", time="00:00", tz="UTC")
    store.add(rem)
    quiet = QuietHours(start="22:00", end="07:00")
    clock = FakeClock(datetime(2020, 1, 1, 23, 0, tzinfo=timezone.utc))
    notifier = RecordingNotifier()
    r1 = deliver_due(store, clock=clock, notifier=notifier, quiet_hours=quiet)
    assert notifier.calls == []
    assert rem.id in r1.pending
    assert store.load()[0].delivery == "pending"

    clock._when = datetime(2020, 1, 2, 8, 0, tzinfo=timezone.utc)
    deliver_due(store, clock=clock, notifier=notifier, quiet_hours=quiet)
    assert len(notifier.calls) == 1
    assert store.load()[0].delivery == "delivered"


def test_pc_desligado_reavalia_uma_vez(tmp_path: Path) -> None:
    """Relógio avança sem entrega; a passagem seguinte notifica uma vez."""

    store = ReminderStore(tmp_path / "r.json")
    rem = build_reminder(text="boot", date="2020-01-01", time="12:00", tz="UTC")
    store.add(rem)
    clock = FakeClock(datetime(2020, 1, 1, 11, 0, tzinfo=timezone.utc))
    notifier = RecordingNotifier()
    deliver_due(store, clock=clock, notifier=notifier)
    assert notifier.calls == []
    assert store.load()[0].delivery == "scheduled"

    clock.advance(hours=5)  # “PC desligado” — ninguém chamou deliver
    deliver_due(store, clock=clock, notifier=notifier)
    assert len(notifier.calls) == 1
    deliver_due(store, clock=clock, notifier=notifier)
    assert len(notifier.calls) == 1


def test_queda_apos_notify_antes_de_delivered(tmp_path: Path, monkeypatch) -> None:
    store = ReminderStore(tmp_path / "r.json")
    rem = build_reminder(text="crash", date="2020-01-01", time="00:00", tz="UTC")
    store.add(rem)
    clock = FakeClock(datetime(2020, 1, 2, tzinfo=timezone.utc))
    notifier = RecordingNotifier()

    real_update = ReminderStore.update
    calls = {"n": 0}

    def selective(self, reminder_id, *, delivery):  # noqa: ANN001
        calls["n"] += 1
        # mark_pending ok; mark_delivered falha (queda)
        if delivery == "delivered":
            raise OSError("queda simulada após notify")
        return real_update(self, reminder_id, delivery=delivery)

    monkeypatch.setattr(ReminderStore, "update", selective)
    try:
        deliver_due(store, clock=clock, notifier=notifier)
    except OSError:
        pass
    assert len(notifier.calls) == 1
    assert store.load()[0].delivery == "pending"

    monkeypatch.setattr(ReminderStore, "update", real_update)
    deliver_due(store, clock=clock, notifier=notifier)
    assert len(notifier.calls) == 2
    assert store.load()[0].delivery == "delivered"


def test_painel_meta_delivery(tmp_path: Path) -> None:
    store = ReminderStore(tmp_path / "r.json")
    future = build_reminder(text="futuro", date="2099-01-01", time="10:00", tz="UTC")
    past = build_reminder(text="passado", date="2020-01-01", time="00:00", tz="UTC")
    store.add(future)
    store.add(past)
    store.mark_pending(past.id)
    items = read_reminders(tmp_path / "r.json")
    by_title = {i.title: i for i in items}
    assert by_title["futuro"].meta["delivery"] == "scheduled"
    assert "vence em" in by_title["futuro"].detail
    assert by_title["passado"].meta["delivery"] == "pending"
    assert "entrega pendente" in by_title["passado"].detail


def test_cli_reminders_once(tmp_path: Path, monkeypatch) -> None:
    rem_path = tmp_path / "reminders.json"
    store = ReminderStore(rem_path)
    rem = build_reminder(text="cli", date="2020-01-01", time="00:00", tz="UTC")
    store.add(rem)
    monkeypatch.setattr(
        "src.assist.delivery.DesktopNotifier",
        lambda: RecordingNotifier(),
    )
    monkeypatch.setattr(
        "src.assist.config.load_assist_config",
        lambda *_a, **_k: AssistConfig(
            apps={},
            search_roots=(),
            routines={},
            reminders_path=rem_path,
            audit_log_path=tmp_path / "a.jsonl",
            ollama_base_url="http://127.0.0.1:9",
            ollama_timeout=1.0,
        ),
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["reminders", "once"])
    assert result.exit_code == 0
    assert "notificados=" in result.output
    assert ReminderStore(rem_path).load()[0].delivery == "delivered"
