"""Laço pressionar-para-falar do assist — mesma sessão/executor do texto."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.assist.session import AssistSession
from src.voice.config import VoiceConfig
from src.voice.mic import MicError, check_mic, record_until_enter
from src.voice.stt import (
    SttError,
    TranscriptResult,
    check_stt,
    is_ambiguous_transcript,
    transcribe_detailed,
)
from src.voice.tts import TtsError, check_tts, speak

YES = frozenset({"s", "sim", "y", "yes", "confirma", "confirmar"})
NO = frozenset({"n", "nao", "não", "cancela", "cancelar", "cancel", "no"})


@dataclass
class TurnTiming:
    label: str
    stt_ms: float = 0.0
    interpret_ms: float = 0.0
    execute_ms: float = 0.0
    tts_ms: float = 0.0

    def dominant(self) -> str:
        pairs = [
            ("transcrição", self.stt_ms),
            ("interpretação", self.interpret_ms),
            ("execução", self.execute_ms),
            ("síntese", self.tts_ms),
        ]
        return max(pairs, key=lambda p: p[1])[0]


@dataclass
class VoiceLoopState:
    turn_index: int = 0
    timings: list[TurnTiming] = field(default_factory=list)
    rehandle: str | None = None


def classify_confirm_reply(text: str, *, avg_logprob: float | None = None) -> str:
    """Devolve yes | no | ambiguous | other."""

    if is_ambiguous_transcript(text, avg_logprob):
        return "ambiguous"
    low = " ".join(text.casefold().split())
    if low in YES:
        return "yes"
    if low in NO:
        return "no"
    return "other"


def format_timing_line(timing: TurnTiming) -> str:
    """Só números e rótulos — sem conteúdo da fala."""

    return (
        f"tempo[{timing.label}] "
        f"stt={timing.stt_ms:.0f}ms "
        f"interpret={timing.interpret_ms:.0f}ms "
        f"exec={timing.execute_ms:.0f}ms "
        f"tts={timing.tts_ms:.0f}ms "
        f"dominante={timing.dominant()}"
    )


class VoiceConfirm:
    """confirm_fn falado: lê a prévia e escuta a resposta."""

    def __init__(
        self,
        *,
        config: VoiceConfig,
        state: VoiceLoopState,
        input_fn: Callable[[str], str] | None = None,
        output_fn: Callable[[str], None] | None = None,
        record_fn: Callable[..., Any] | None = None,
        transcribe_fn: Callable[..., TranscriptResult] | None = None,
        speak_fn: Callable[[str, VoiceConfig], Any] | None = None,
    ) -> None:
        self.config = config
        self.state = state
        self.input_fn = input_fn
        self.output_fn = output_fn or (lambda _m: None)
        self.record_fn = record_fn or record_until_enter
        self.transcribe_fn = transcribe_fn or transcribe_detailed
        self.speak_fn = speak_fn or speak

    def __call__(self, preview: str) -> bool:
        self.output_fn(preview)
        try:
            self.speak_fn(preview, self.config)
        except TtsError as exc:
            self.output_fn(f"TTS indisponível na prévia: {exc}")

        try:
            result = self._capture()
        except SttError as exc:
            self.output_fn(f"Transcrição na confirmação falhou: {exc}")
            return False
        except MicError as exc:
            self.output_fn(f"Microfone na confirmação: {exc}")
            return False

        kind = classify_confirm_reply(result.text, avg_logprob=result.avg_logprob)
        if kind == "yes":
            return True
        if kind in {"no", "ambiguous"}:
            self.output_fn(
                f"Confirmação não concedida ({kind}). Nada foi executado."
            )
            return False
        self.state.rehandle = result.text
        self.output_fn(
            "Resposta não é sim/cancela — trato como novo pedido "
            "(gera outra prévia se for lembrete)."
        )
        return False

    def _capture(self) -> TranscriptResult:
        wav = self.record_fn(
            self.config,
            input_fn=self.input_fn,
            output_fn=self.output_fn,
        )
        try:
            return self.transcribe_fn(wav, self.config)
        finally:
            try:
                wav.unlink(missing_ok=True)
            except OSError:
                pass


def run_voice_session(
    session: AssistSession,
    voice_config: VoiceConfig,
    *,
    input_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], None] | None = None,
    err_fn: Callable[[str], None] | None = None,
    record_fn: Callable[..., Any] | None = None,
    transcribe_fn: Callable[..., TranscriptResult] | None = None,
    speak_fn: Callable[[str, VoiceConfig], Any] | None = None,
    max_turns: int | None = None,
) -> VoiceLoopState:
    """Pressionar para falar → mesma sessão. Sem gravação contínua / nuvem / log de áudio."""

    say = output_fn or (lambda _m: None)
    err = err_fn or say
    state = VoiceLoopState()
    rec = record_fn or record_until_enter
    tr = transcribe_fn or transcribe_detailed
    spk = speak_fn or speak
    wait = input_fn

    ok_mic, msg_mic = check_mic()
    ok_stt, msg_stt = check_stt()
    if not ok_mic or not ok_stt:
        err(f"{msg_mic} {msg_stt}".strip())
        err("Sem microfone/STT — continue com `python yby.py assist` (texto).")
        return state

    confirm = VoiceConfirm(
        config=voice_config,
        state=state,
        input_fn=wait,
        output_fn=say,
        record_fn=rec,
        transcribe_fn=tr,
        speak_fn=spk,
    )
    session.confirm_fn = confirm

    say(
        "YBY assist (voz). Pressionar para falar: Enter para parar a gravação. "
        "Fale 'sair' para encerrar. Ctrl+C também encerra."
    )
    for msg in session.startup_messages():
        say(msg)

    turns = 0
    while max_turns is None or turns < max_turns:
        if state.rehandle is not None:
            utterance = state.rehandle
            state.rehandle = None
            stt_ms = 0.0
        else:
            try:
                t0 = time.perf_counter()
                wav = rec(voice_config, input_fn=wait, output_fn=say)
                try:
                    detailed = tr(wav, voice_config)
                finally:
                    try:
                        wav.unlink(missing_ok=True)
                    except OSError:
                        pass
                stt_ms = (time.perf_counter() - t0) * 1000
            except (EOFError, KeyboardInterrupt):
                say("\nEncerrado.")
                break
            except MicError as exc:
                err(f"Microfone: {exc}. Digite o pedido (texto) ou Enter vazio para pular.")
                utterance, stt_ms = _fallback_text(wait, err)
                if utterance is None:
                    break
                if utterance == "":
                    continue
                detailed = TranscriptResult(text=utterance)
            except SttError as exc:
                err(
                    f"Transcrição falhou: {exc}. Nada foi executado. "
                    "Digite o pedido ou Enter vazio para pular."
                )
                utterance, stt_ms = _fallback_text(wait, err)
                if utterance is None:
                    break
                if utterance == "":
                    continue
                detailed = TranscriptResult(text=utterance)
            else:
                if detailed.ambiguous:
                    err(
                        "Transcrição ambígua — não confirmo nem executo. "
                        "Digite o pedido ou Enter vazio para pular."
                    )
                    utterance, stt_ms = _fallback_text(wait, err)
                    if utterance is None:
                        break
                    if utterance == "":
                        continue
                    detailed = TranscriptResult(text=utterance)
                utterance = detailed.text
                say(f"você: {utterance}")

        if utterance.strip().casefold() in {"sair", "exit", "quit"}:
            say("Até logo.")
            break

        label = _label_for_turn(session, state.turn_index, utterance)
        timing = TurnTiming(label=label, stt_ms=stt_ms)

        t1 = time.perf_counter()
        outcome = session.handle(utterance)
        elapsed = (time.perf_counter() - t1) * 1000
        if outcome.result is not None:
            timing.interpret_ms = elapsed * 0.4
            timing.execute_ms = elapsed * 0.6
        else:
            timing.interpret_ms = elapsed

        if outcome.user_message == "__EXIT__":
            say("Até logo.")
            state.timings.append(timing)
            err(format_timing_line(timing))
            break

        say(outcome.user_message)

        if state.rehandle is not None:
            state.timings.append(timing)
            err(format_timing_line(timing))
            state.turn_index += 1
            turns += 1
            continue

        if outcome.user_message.strip():
            t2 = time.perf_counter()
            try:
                path = spk(outcome.user_message, voice_config)
                if path is not None:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass
            except TtsError as exc:
                err(f"TTS indisponível: {exc} (ação já refletida acima; não repito).")
            timing.tts_ms = (time.perf_counter() - t2) * 1000

        state.timings.append(timing)
        err(format_timing_line(timing))
        state.turn_index += 1
        turns += 1

    return state


def _fallback_text(
    wait: Callable[[str], str] | None,
    err: Callable[[str], None],
) -> tuple[str | None, float]:
    try:
        text = (wait or input)("assist-texto> ")
    except (EOFError, KeyboardInterrupt):
        err("\nEncerrado.")
        return None, 0.0
    return text.strip(), 0.0


def _label_for_turn(session: AssistSession, index: int, utterance: str) -> str:
    from src.assist.config import match_routine_alias

    if match_routine_alias(session.config, utterance) is not None:
        return "rotina_sem_ollama"
    if index == 0:
        return "primeira"
    return "seguinte"


def voice_available(config: VoiceConfig) -> tuple[bool, str]:
    ok_mic, msg_mic = check_mic()
    ok_stt, msg_stt = check_stt()
    ok_tts, msg_tts = check_tts(config)
    if not ok_mic or not ok_stt:
        return False, f"{msg_mic} {msg_stt}".strip()
    if not ok_tts:
        return True, f"(TTS opcional) {msg_tts}"
    return True, "voz pronta"
