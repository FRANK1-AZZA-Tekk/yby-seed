"""Regressões do TTS sem Piper, player ou modelos reais."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.voice import tts


@pytest.fixture
def rig(monkeypatch, tmp_path):
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"fake model")
    config = SimpleNamespace(piper_bin="piper", piper_model=str(model), play_bin="aplay")
    state = SimpleNamespace(mode="success", paths=[], calls=[])
    original_temp = tts._temp_wav

    def temp():
        path = original_temp()
        state.paths.append(path)
        return path

    def which(name):
        if name == "aplay" and state.mode == "missing_player":
            return None
        return f"/fake/{name}"

    def run(args, **kwargs):
        state.calls.append((args, kwargs))
        is_piper = args[0] == "piper"
        stage = "piper" if is_piper else "player"
        if state.mode == f"{stage}_missing":
            raise FileNotFoundError(stage)
        if state.mode == f"{stage}_permission":
            raise PermissionError(stage)
        if state.mode == f"{stage}_timeout":
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])
        if state.mode == f"{stage}_cancel":
            raise KeyboardInterrupt
        if is_piper and state.mode != "empty_output":
            Path(args[-1]).write_bytes(b"simulated audio")
        code = 1 if state.mode == f"{stage}_error" else 0
        return SimpleNamespace(returncode=code, stderr=b"simulated failure" if code else b"")

    monkeypatch.setattr(tts, "_temp_wav", temp)
    monkeypatch.setattr(tts.shutil, "which", which)
    monkeypatch.setattr(tts.subprocess, "run", run)
    yield config, state
    for path in state.paths:
        path.unlink(missing_ok=True)


@pytest.mark.parametrize(
    "mode, message",
    [
        ("piper_missing", "executar o Piper"),
        ("piper_permission", "executar o Piper"),
        ("piper_timeout", "Piper demorou"),
        ("piper_error", "simulated failure"),
        ("empty_output", "não gerou áudio"),
        ("missing_player", "não encontrado"),
        ("player_missing", "executar o player"),
        ("player_permission", "executar o player"),
        ("player_timeout", "Reprodução de áudio demorou"),
        ("player_error", "Player falhou"),
    ],
)
def test_failure_is_tts_error_and_removes_wav(rig, mode, message):
    config, state = rig
    state.mode = mode
    with pytest.raises(tts.TtsError, match=message):
        tts.speak("Teste YBY", config)
    assert len(state.paths) == 1
    assert not state.paths[0].exists()


@pytest.mark.parametrize("mode", ["piper_cancel", "player_cancel"])
def test_cancel_removes_wav_and_propagates(rig, mode):
    config, state = rig
    state.mode = mode
    with pytest.raises(KeyboardInterrupt):
        tts.speak("Teste YBY", config)
    assert not state.paths[0].exists()


def test_success_returns_wav_owned_by_caller(rig):
    config, state = rig
    path = tts.speak("  Olá YBY  ", config)
    assert path.exists()
    assert path == state.paths[0]
    assert len(state.calls) == 2
    assert state.calls[0][1]["input"] == "Olá YBY".encode()
    assert state.calls[1][0][1] == str(path)


def test_empty_text_does_not_create_file(rig):
    config, state = rig
    with pytest.raises(tts.TtsError, match="Texto vazio"):
        tts.speak("  ", config)
    assert not state.paths
    assert not state.calls


def test_temp_creation_failure_is_tts_error(rig, monkeypatch):
    config, state = rig

    def fail():
        raise PermissionError("temporary directory")

    monkeypatch.setattr(tts, "_temp_wav", fail)
    with pytest.raises(tts.TtsError, match="criar o WAV"):
        tts.speak("Teste", config)
    assert not state.calls


def test_cleanup_failure_preserves_original_error(rig, monkeypatch):
    config, state = rig
    state.mode = "player_timeout"
    original_unlink = Path.unlink

    def fail(path, *args, **kwargs):
        if path in state.paths:
            raise PermissionError("cleanup denied")
        return original_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail)
        with pytest.raises(tts.TtsError, match="Reprodução de áudio demorou") as error:
            tts.speak("Teste", config)
        assert any("remover o WAV" in note for note in error.value.__notes__)
