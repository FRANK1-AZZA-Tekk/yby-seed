"""assist --voice: mesma sessão/permissões do texto (mic/STT/TTS substituíveis)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from src.assist.config import AssistConfig, AppEntry, RoutineEntry, RoutineStep
from src.assist.reminders import ReminderStore
from src.assist.router import ScriptedAssistPlanner
from src.assist.session import AssistSession
from src.assist.types import ToolProposal
from src.assist.voice_loop import (
    VoiceConfirm,
    VoiceLoopState,
    classify_confirm_reply,
    format_timing_line,
    run_voice_session,
)
from src.main import cli
from src.voice.config import VoiceConfig
from src.voice.stt import TranscriptResult


def _vcfg() -> VoiceConfig:
    return VoiceConfig(
        whisper_model="base",
        whisper_device="cpu",
        whisper_compute_type="int8",
        sample_rate=16_000,
        piper_bin="piper",
        piper_model="/tmp/fake.onnx",
        play_bin="aplay",
        max_seconds=30,
    )


def _cfg(tmp_path: Path) -> AssistConfig:
    return AssistConfig(
        apps={"obsidian": AppEntry(argv=("obsidian",))},
        search_roots=(tmp_path / "docs",),
        routines={
            "modo_estudo": RoutineEntry(
                aliases=("modo estudo",),
                steps=(RoutineStep("app.open", {"name": "obsidian"}),),
            )
        },
        reminders_path=tmp_path / "r.json",
        audit_log_path=tmp_path / "a.jsonl",
        ollama_base_url="http://127.0.0.1:9",
        ollama_timeout=1.0,
    )


def test_classify_confirm_yes_no_ambiguous() -> None:
    assert classify_confirm_reply("sim") == "yes"
    assert classify_confirm_reply("cancela") == "no"
    assert classify_confirm_reply("") == "ambiguous"
    assert classify_confirm_reply("muda para 14:00") == "other"
    assert classify_confirm_reply("x", avg_logprob=-2.0) == "ambiguous"


def test_voice_o_segundo_seleciona_nao_abre(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("src.assist.voice_loop.check_mic", lambda: (True, "ok"))
    monkeypatch.setattr("src.assist.voice_loop.check_stt", lambda: (True, "ok"))
    root = tmp_path / "docs"
    root.mkdir()
    (root / "a-relatorio.txt").write_text("1", encoding="utf-8")
    (root / "b-relatorio.txt").write_text("2", encoding="utf-8")
    cfg = _cfg(tmp_path)
    session = AssistSession(
        config=cfg,
        planner=ScriptedAssistPlanner(
            [ToolProposal("files.find", {"query": "relatorio", "limit": 10}, "ollama")]
        ),
        confirm_fn=lambda _m: True,
    )
    spoken: list[str] = []
    transcripts = iter(
        [
            TranscriptResult("acha relatorio"),
            TranscriptResult("o segundo"),
            TranscriptResult("sair"),
        ]
    )

    def fake_record(config, **_k):  # noqa: ANN001
        p = tmp_path / "t.wav"
        p.write_bytes(b"RIFF")
        return p

    def fake_tr(_wav, _cfg):  # noqa: ANN001
        return next(transcripts)

    def fake_speak(text: str, _cfg):  # noqa: ANN001
        spoken.append(text)
        return None

    state = run_voice_session(
        session,
        _vcfg(),
        record_fn=fake_record,
        transcribe_fn=fake_tr,
        speak_fn=fake_speak,
        max_turns=10,
    )
    assert state.turn_index >= 1
    assert any("Não abri" in t for t in spoken)


def test_voice_cancela_nao_confirma_lembrete(tmp_path: Path) -> None:
    store = ReminderStore(tmp_path / "r.json")
    session = AssistSession(
        config=_cfg(tmp_path),
        planner=ScriptedAssistPlanner(
            [
                ToolProposal(
                    "reminder.create",
                    {
                        "text": "estudar",
                        "date": "2026-12-01",
                        "time": "10:00",
                        "tz": "UTC",
                    },
                    "ollama",
                )
            ]
        ),
        reminder_store=store,
        confirm_fn=lambda _m: True,  # substituído pelo VoiceConfirm
    )
    state = VoiceLoopState()
    replies = iter([TranscriptResult("cancela")])

    def fake_record(config, **_k):  # noqa: ANN001
        p = tmp_path / "c.wav"
        p.write_bytes(b"x")
        return p

    confirm = VoiceConfirm(
        config=_vcfg(),
        state=state,
        record_fn=fake_record,
        transcribe_fn=lambda *_a, **_k: next(replies),
        speak_fn=lambda *_a, **_k: None,
        output_fn=lambda _m: None,
    )
    session.confirm_fn = confirm
    out = session.handle("lembrete")
    assert out.result is not None
    assert out.result.ok is False
    assert store.load() == []


def test_voice_correcao_horario_nova_previa(tmp_path: Path) -> None:
    store = ReminderStore(tmp_path / "r.json")
    session = AssistSession(
        config=_cfg(tmp_path),
        planner=ScriptedAssistPlanner(
            [
                ToolProposal(
                    "reminder.create",
                    {
                        "text": "estudar",
                        "date": "2026-12-01",
                        "time": "10:00",
                        "tz": "UTC",
                    },
                    "ollama",
                ),
                ToolProposal(
                    "reminder.create",
                    {
                        "text": "estudar",
                        "date": "2026-12-01",
                        "time": "14:00",
                        "tz": "UTC",
                    },
                    "ollama",
                ),
            ]
        ),
        reminder_store=store,
        confirm_fn=lambda _m: True,
    )
    state = VoiceLoopState()
    # 1ª confirmação: corrige hora; 2ª: sim
    replies = iter(
        [
            TranscriptResult("muda para 14:00"),
            TranscriptResult("sim"),
        ]
    )

    def fake_record(config, **_k):  # noqa: ANN001
        p = tmp_path / "c.wav"
        p.write_bytes(b"x")
        return p

    confirm = VoiceConfirm(
        config=_vcfg(),
        state=state,
        record_fn=fake_record,
        transcribe_fn=lambda *_a, **_k: next(replies),
        speak_fn=lambda *_a, **_k: None,
        output_fn=lambda _m: None,
    )
    session.confirm_fn = confirm
    first = session.handle("lembrete")
    assert first.result is not None and first.result.ok is False
    assert state.rehandle == "muda para 14:00"
    # rehandle como texto (mesmo executor)
    second = session.handle(
        "lembrete"
    )  # planner devolve 2ª proposta 14:00; confirm diz sim
    assert second.result is not None and second.result.ok is True
    assert "14:00" in second.result.narration
    assert len(store.load()) == 1


def test_tts_falha_nao_repete_acao(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("src.assist.voice_loop.check_mic", lambda: (True, "ok"))
    monkeypatch.setattr("src.assist.voice_loop.check_stt", lambda: (True, "ok"))
    launches: list[tuple[str, ...]] = []
    session = AssistSession(
        config=_cfg(tmp_path),
        planner=None,
        launcher=lambda argv: launches.append(tuple(argv)),
        confirm_fn=lambda _m: True,
    )
    from src.voice.tts import TtsError

    transcripts = iter([TranscriptResult("modo estudo"), TranscriptResult("sair")])

    def fake_record(config, **_k):  # noqa: ANN001
        p = tmp_path / "t.wav"
        p.write_bytes(b"x")
        return p

    def boom(_text: str, _cfg):  # noqa: ANN001
        raise TtsError("piper down")

    run_voice_session(
        session,
        _vcfg(),
        record_fn=fake_record,
        transcribe_fn=lambda *_a, **_k: next(transcripts),
        speak_fn=boom,
        max_turns=5,
    )
    assert launches == [("obsidian",)]


def test_timing_sem_conteudo() -> None:
    from src.assist.voice_loop import TurnTiming

    line = format_timing_line(
        TurnTiming("primeira", stt_ms=10, interpret_ms=20, execute_ms=5, tts_ms=1)
    )
    assert "stt=10ms" in line
    assert "dominante=interpretação" in line
    assert "água" not in line


@pytest.mark.skip(reason="desempenho pendente: sem fone/modelo real no PC Hub")
def test_desempenho_hub_pendente() -> None:
    """Não marca como aprovado sem medição real no hub."""

    raise AssertionError("não deve rodar")


def test_listen_e_ask_voice_inalterados(monkeypatch) -> None:
    """Regressão: listen / ask --voice seguem no HybridEngine."""

    from src.engine.hybrid import EngineReply
    from src.voice.session import VoiceTurn

    class _Eng:
        def reply(self, prompt: str, *, explicit_heavy: bool = False) -> EngineReply:
            return EngineReply("ok", "local", "qwen2.5-coder:3b", ("local",), None)

    monkeypatch.setattr("src.main.build_engine", lambda: _Eng())
    monkeypatch.setattr(
        "src.main.listen_once",
        lambda *a, **k: VoiceTurn("oi", _Eng().reply("oi"), None, None),
    )
    runner = CliRunner()
    assert runner.invoke(cli, ["ask", "--voice"]).exit_code == 0
    assert runner.invoke(cli, ["listen"]).exit_code == 0
