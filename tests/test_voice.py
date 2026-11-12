"""Camada de voz com STT/TTS/mic mockados. Sem modelos reais."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from src.engine.hybrid import EngineReply
from src.main import cli
from src.voice.config import VoiceConfig
from src.voice.session import VoiceError, VoiceTurn, availability, listen_once
from src.voice.stt import SttError, check_stt, transcribe
from src.voice.tts import TtsError, check_tts, speak


def _cfg(**overrides: object) -> VoiceConfig:
    base = dict(
        whisper_model="base",
        whisper_device="cpu",
        whisper_compute_type="int8",
        sample_rate=16_000,
        piper_bin="piper",
        piper_model="/tmp/fake-voice.onnx",
        play_bin="aplay",
    )
    base.update(overrides)
    return VoiceConfig(**base)  # type: ignore[arg-type]


class _ScriptedEngine:
    def __init__(self, reply: EngineReply) -> None:
        self.reply_value = reply
        self.calls: list[dict[str, object]] = []

    def reply(self, prompt: str, *, explicit_heavy: bool = False) -> EngineReply:
        self.calls.append({"prompt": prompt, "explicit_heavy": explicit_heavy})
        return self.reply_value


def test_check_stt_sem_pacote(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def _fake(name, *args, **kwargs):
        if name == "faster_whisper" or name.startswith("faster_whisper"):
            raise ImportError("nope")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake)
    ok, msg = check_stt()
    assert ok is False
    assert "faster-whisper" in msg


def test_transcribe_sem_pacote_levanta(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.voice.stt.check_stt",
        lambda: (
            False,
            "faster-whisper não instalado. Rode: pip install -r requirements-voice.txt",
        ),
    )
    try:
        transcribe(Path("/tmp/x.wav"), _cfg())
        raise AssertionError("deveria falhar")
    except SttError as exc:
        assert "faster-whisper" in str(exc)


def test_transcribe_arquivo_ausente(monkeypatch) -> None:
    import sys
    import types

    fake = types.ModuleType("faster_whisper")

    class _Boom:
        def __init__(self, *a, **k):
            raise AssertionError("não deveria carregar modelo")

    fake.WhisperModel = _Boom
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)
    monkeypatch.setattr("src.voice.stt.check_stt", lambda: (True, "ok"))

    try:
        transcribe(Path("/tmp/yby-nao-existe-xyz.wav"), _cfg())
        raise AssertionError("deveria falhar")
    except SttError as exc:
        assert "não encontrado" in str(exc)


def test_check_tts_sem_binario(monkeypatch) -> None:
    monkeypatch.setattr("src.voice.tts.shutil.which", lambda _name: None)
    ok, msg = check_tts(_cfg())
    assert ok is False
    assert "piper" in msg.lower()


def test_check_tts_sem_modelo(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("src.voice.tts.shutil.which", lambda _name: "/usr/bin/piper")
    ok, msg = check_tts(_cfg(piper_model=""))
    assert ok is False
    assert "YBY_PIPER_MODEL" in msg


def test_speak_degrada_sem_piper(monkeypatch) -> None:
    monkeypatch.setattr("src.voice.tts.check_tts", lambda _c: (False, "sem piper"))
    try:
        speak("oi", _cfg())
        raise AssertionError("deveria falhar")
    except TtsError as exc:
        assert "sem piper" in str(exc)


def test_availability_exige_mic_e_stt(monkeypatch) -> None:
    monkeypatch.setattr("src.voice.session.check_mic", lambda: (False, "sem mic"))
    monkeypatch.setattr("src.voice.session.check_stt", lambda: (True, "ok"))
    monkeypatch.setattr("src.voice.session.check_tts", lambda _c: (True, "ok"))
    ok, msg = availability(_cfg())
    assert ok is False
    assert "sem mic" in msg


def test_listen_once_fluxo_completo(monkeypatch, tmp_path: Path) -> None:
    wav = tmp_path / "in.wav"
    wav.write_bytes(b"RIFF....")
    out = tmp_path / "out.wav"
    out.write_bytes(b"RIFF....")

    monkeypatch.setattr("src.voice.session.availability", lambda _c: (True, "ok"))
    monkeypatch.setattr(
        "src.voice.session.record_until_enter",
        lambda *_a, **_k: wav,
    )
    monkeypatch.setattr("src.voice.session.transcribe", lambda *_a, **_k: "explica lista")
    monkeypatch.setattr("src.voice.session.speak", lambda *_a, **_k: out)

    engine = _ScriptedEngine(
        EngineReply(
            text="uma lista guarda itens",
            provider="local",
            model="qwen2.5-coder:3b",
            reasons=("pedido dentro do limite local",),
            notice=None,
        )
    )
    turn = listen_once(engine, _cfg(), input_fn=lambda _p: "", output_fn=lambda _m: None)

    assert turn.transcript == "explica lista"
    assert turn.reply.text == "uma lista guarda itens"
    assert turn.tts_path == out
    assert engine.calls == [{"prompt": "explica lista", "explicit_heavy": False}]
    assert not wav.exists()  # limpeza do áudio de entrada


def test_listen_once_tts_opcional(monkeypatch, tmp_path: Path) -> None:
    wav = tmp_path / "in.wav"
    wav.write_bytes(b"x")
    monkeypatch.setattr("src.voice.session.availability", lambda _c: (True, "ok"))
    monkeypatch.setattr("src.voice.session.record_until_enter", lambda *_a, **_k: wav)
    monkeypatch.setattr("src.voice.session.transcribe", lambda *_a, **_k: "oi")

    def _boom(*_a, **_k):
        raise TtsError("sem piper")

    monkeypatch.setattr("src.voice.session.speak", _boom)
    engine = _ScriptedEngine(EngineReply("olá", "local", "qwen2.5-coder:3b", ("ok",), None))
    notices: list[str] = []
    turn = listen_once(
        engine,
        _cfg(),
        input_fn=lambda _p: "",
        output_fn=notices.append,
    )
    assert turn.tts_path is None
    assert turn.tts_notice == "sem piper"
    assert turn.reply.text == "olá"


def test_listen_cli(monkeypatch) -> None:
    engine = _ScriptedEngine(
        EngineReply("resposta falada", "local", "qwen2.5-coder:3b", ("ok",), None)
    )
    monkeypatch.setattr("src.main.build_engine", lambda: engine)
    monkeypatch.setattr(
        "src.main.listen_once",
        lambda *_a, **_k: VoiceTurn(
            transcript="oi",
            reply=engine.reply_value,
            tts_path=None,
            tts_notice="sem piper",
        ),
    )
    result = CliRunner().invoke(cli, ["listen"])
    assert result.exit_code == 0
    assert "resposta falada" in result.output


def test_ask_voice_flag(monkeypatch) -> None:
    engine = _ScriptedEngine(EngineReply("ok voz", "local", "qwen2.5-coder:3b", ("ok",), None))
    monkeypatch.setattr("src.main.build_engine", lambda: engine)
    monkeypatch.setattr(
        "src.main.listen_once",
        lambda *_a, **_k: VoiceTurn(
            transcript="teste",
            reply=engine.reply_value,
            tts_path=None,
            tts_notice=None,
        ),
    )
    result = CliRunner().invoke(cli, ["ask", "--voice"])
    assert result.exit_code == 0
    assert "ok voz" in result.output


def test_ask_voice_erro_degrada_para_mensagem(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.main.build_engine", lambda: _ScriptedEngine(EngineReply("", "none", "", ("x",), None))
    )
    monkeypatch.setattr(
        "src.main.listen_once",
        lambda *_a, **_k: (_ for _ in ()).throw(VoiceError("sem mic")),
    )
    result = CliRunner().invoke(cli, ["ask", "--voice"])
    assert result.exit_code == 1
    assert "sem mic" in result.output
    assert "Texto continua disponível" in result.output


def test_ask_texto_ainda_funciona(monkeypatch) -> None:
    engine = _ScriptedEngine(EngineReply("só texto", "local", "qwen2.5-coder:3b", ("ok",), None))
    monkeypatch.setattr("src.main.build_engine", lambda: engine)
    result = CliRunner().invoke(cli, ["ask", "oi"])
    assert result.exit_code == 0
    assert "só texto" in result.output
