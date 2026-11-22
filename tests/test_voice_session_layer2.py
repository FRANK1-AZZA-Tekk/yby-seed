"""Integração da sessão de voz com mic, STT e TTS simulados."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.engine.hybrid import EngineReply
from src.voice import session
from src.voice.config import VoiceConfig


@pytest.fixture
def voice_session(monkeypatch, tmp_path):
    wav = tmp_path / "in.wav"
    wav.write_bytes(b"simulated audio")
    config = VoiceConfig(
        whisper_model="base",
        whisper_device="cpu",
        whisper_compute_type="int8",
        sample_rate=16_000,
        piper_bin="piper",
        piper_model="/tmp/fake-voice.onnx",
        play_bin="aplay",
    )
    reply = EngineReply("resposta", "local", "qwen2.5-coder:3b", ("ok",), None)
    engine = SimpleNamespace(reply=Mock(return_value=reply))
    speaker = Mock(side_effect=AssertionError("TTS não deveria ser chamado"))
    monkeypatch.setattr(session, "availability", lambda _config: (True, "ok"))
    monkeypatch.setattr(session, "record_until_enter", lambda *args, **kwargs: wav)
    monkeypatch.setattr(session, "transcribe", lambda *args, **kwargs: "consulta")
    monkeypatch.setattr(session, "speak", speaker)
    return SimpleNamespace(
        wav=wav, config=config, reply=reply, engine=engine, speaker=speaker
    )


def test_engine_failure_reports_stage_and_removes_input(voice_session):
    rig = voice_session
    original = RuntimeError("engine offline")
    rig.engine.reply.side_effect = original
    notices = []

    with pytest.raises(session.VoiceError, match="Engine falhou após a transcrição") as error:
        session.listen_once(rig.engine, rig.config, output_fn=notices.append)

    assert error.value.__cause__ is original
    assert not rig.wav.exists()
    assert "você: consulta" in notices
    rig.speaker.assert_not_called()


def test_explicit_heavy_is_forwarded_without_real_tts(voice_session):
    rig = voice_session
    turn = session.listen_once(
        rig.engine, rig.config, explicit_heavy=True, speak_reply=False
    )

    rig.engine.reply.assert_called_once_with("consulta", explicit_heavy=True)
    assert turn.transcript == "consulta"
    assert turn.reply is rig.reply
    assert not rig.wav.exists()
    rig.speaker.assert_not_called()


def test_disabled_tts_preserves_text_reply(voice_session):
    rig = voice_session
    turn = session.listen_once(rig.engine, rig.config, speak_reply=False)

    rig.engine.reply.assert_called_once_with("consulta", explicit_heavy=False)
    rig.speaker.assert_not_called()
    assert turn.reply.text == "resposta"
    assert turn.tts_path is None
    assert turn.tts_notice is None
    assert not rig.wav.exists()
