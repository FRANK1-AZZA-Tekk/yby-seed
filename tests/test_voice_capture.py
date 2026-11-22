"""Regressões da captura sem hardware ou dependências opcionais reais."""

import sys
import wave
from io import StringIO
from types import SimpleNamespace

import pytest

from src.voice import mic


class Chunk:
    def __init__(self, n):
        self.n = n

    def __len__(self):
        return self.n

    def __getitem__(self, key):
        return Chunk(len(range(self.n)[key]))

    def copy(self):
        return Chunk(self.n)

    def tobytes(self):
        return b"\x00\x00" * self.n


@pytest.fixture
def capture(monkeypatch):
    monkeypatch.delenv("YBY_VOICE_INPUT_DEVICE", raising=False)
    state = SimpleNamespace(chunks=[4], closed=False, start_error=False, status=None)

    class Stream:
        active = True

        def __init__(self, **kwargs):
            state.kwargs = kwargs

        def __enter__(self):
            if state.start_error:
                raise RuntimeError("start error")
            for size in state.chunks:
                state.kwargs["callback"](Chunk(size), size, None, state.status)
            return self

        def __exit__(self, *args):
            self.close()

        def close(self):
            state.closed = True
            self.active = False

    def query(device, kind):
        state.selected = device
        return {"name": "Fake input", "max_input_channels": 1}

    sd = SimpleNamespace(
        InputStream=Stream, query_devices=query, check_input_settings=lambda **kwargs: None
    )
    np = SimpleNamespace(concatenate=lambda frames, axis=0: Chunk(sum(map(len, frames))))
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    monkeypatch.setitem(sys.modules, "numpy", np)
    monkeypatch.setattr(mic, "check_mic", lambda: (True, "ok"))
    monkeypatch.setattr(mic, "_terminal_stop", lambda timeout: True)
    return state, sd


def config():
    return SimpleNamespace(sample_rate=4, max_seconds=1)


def test_limit_does_not_wait_for_enter(capture):
    state, _ = capture
    path = mic.record_until_enter(
        config(), input_fn=lambda _: pytest.fail("Não deve esperar Enter no limite")
    )
    try:
        assert state.closed
        with wave.open(str(path)) as wav:
            assert wav.getnframes() == 4
    finally:
        path.unlink(missing_ok=True)


def test_last_chunk_is_trimmed(capture):
    state, _ = capture
    state.chunks = [3, 3]
    path = mic.record_until_enter(config())
    try:
        with wave.open(str(path)) as wav:
            assert wav.getnframes() == 4
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.parametrize("raw, expected", [("7", 7), ("Baseus", "Baseus"), ("", None)])
def test_selected_device(capture, monkeypatch, raw, expected):
    state, _ = capture
    monkeypatch.setenv("YBY_VOICE_INPUT_DEVICE", raw)
    path = mic.record_until_enter(config())
    try:
        assert state.selected == expected
        assert state.kwargs["device"] == expected
    finally:
        path.unlink(missing_ok=True)


def test_invalid_input_fails_before_stream(capture):
    state, sd = capture

    def fail(**kwargs):
        raise ValueError("unsupported rate")

    sd.check_input_settings = fail
    with pytest.raises(mic.MicError, match="Entrada de áudio inválida"):
        mic.record_until_enter(config())
    assert not hasattr(state, "kwargs")


def test_empty_capture_closes(capture):
    state, _ = capture
    state.chunks = []
    with pytest.raises(mic.MicError, match="Nenhum áudio"):
        mic.record_until_enter(config())
    assert state.closed


@pytest.mark.parametrize("error", [KeyboardInterrupt, EOFError])
def test_input_error_closes(capture, error):
    state, _ = capture
    state.chunks = [1]

    def fail(_):
        raise error()

    expected = KeyboardInterrupt if error is KeyboardInterrupt else mic.MicError
    with pytest.raises(expected):
        mic.record_until_enter(config(), input_fn=fail)
    assert state.closed


def test_start_failure_closes(capture):
    state, _ = capture
    state.start_error = True
    with pytest.raises(mic.MicError, match="Falha durante"):
        mic.record_until_enter(config())
    assert state.closed


def test_deadline_without_samples(capture, monkeypatch):
    state, _ = capture
    state.chunks = []
    ticks = iter([0.0, 2.0, 2.0])
    monkeypatch.setattr(mic.time, "monotonic", lambda: next(ticks))
    with pytest.raises(mic.MicError, match="Nenhum áudio"):
        mic.record_until_enter(config())
    assert state.closed


def test_partial_wav_removed(capture, monkeypatch, tmp_path):
    state, _ = capture
    partial = tmp_path / "partial.wav"
    partial.touch()
    monkeypatch.setattr(mic, "_temp_wav", lambda: partial)

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(mic.wave, "open", fail)
    with pytest.raises(mic.MicError, match="salvar"):
        mic.record_until_enter(config())
    assert state.closed
    assert not partial.exists()


def test_status_output_happens_after_close(capture):
    state, _ = capture
    state.status = "overflow"
    notices = []

    def say(message):
        if message.startswith("Aviso da captura"):
            assert state.closed
        notices.append(message)

    path = mic.record_until_enter(config(), output_fn=say)
    path.unlink(missing_ok=True)
    assert any("overflow" in message for message in notices)


@pytest.mark.parametrize("text, raises", [("\n", False), ("", True)])
def test_terminal_enter_and_eof(monkeypatch, text, raises):
    monkeypatch.setattr(mic.sys, "stdin", StringIO(text))
    monkeypatch.setattr(mic.select, "select", lambda *args: ([mic.sys.stdin], [], []))
    if raises:
        with pytest.raises(mic.MicError, match="EOF"):
            mic._terminal_stop(0.01)
    else:
        assert mic._terminal_stop(0.01)
