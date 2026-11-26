"""Simulador offline e determinístico do YBY Glass G0.

Sem câmera, microfone, rede ou dispositivo: frames e áudio são sintéticos e
roteirizados pelo teste. O relógio é injetável.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from src.yby.glass.contracts import (
    ARM_TTL_SECONDS,
    CAPTURE_TTL_SECONDS,
    GLASS_PERMISSIONS,
    MAX_CAPTURE_BYTES,
    GlassCaptureError,
    GlassError,
    GlassExpiredError,
    GlassPayloadError,
    GlassState,
    GlassStateError,
    HudPayloadError,
    HudPolicy,
    PerceptionContent,
    PerceptionResult,
    PerceptionTool,
    hud_payload_bytes,
    perception_result_json,
    validate_hud_payload,
)

CaptureKind = Literal["frame", "audio"]

_FRAME_TOOLS = frozenset(
    {"glass_capture_frame", "glass_describe_frame", "glass_read_visible_text", "glass_find_object"}
)
_AUDIO_TOOLS = frozenset({"glass_transcribe_audio"})
_IN_FLIGHT: frozenset[str] = frozenset({"capturing", "processing", "awaiting_retention_decision"})


@dataclass
class FakeClock:
    """Relógio controlado pelo teste (segundos desde a época)."""

    now: float = 1_800_000_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass(frozen=True)
class SyntheticFrame:
    data: bytes = b"\x00" * 1024
    width: int = 320
    height: int = 240
    description: str = "cena sintética"
    visible_text: tuple[str, ...] = ()
    objects: tuple[str, ...] = ()
    fail_processing: bool = False


@dataclass(frozen=True)
class SyntheticAudio:
    data: bytes = b"\x00" * 2048
    duration_ms: int = 1000
    transcript: str = "fala sintética"
    fail_processing: bool = False


class FakeGlassCapture:
    """Fonte de captura roteirizada. Não acessa hardware."""

    def __init__(
        self,
        frames: Iterable[SyntheticFrame] = (),
        audio: Iterable[SyntheticAudio] = (),
        *,
        fail_capture: bool = False,
        on_capture: Callable[[], None] | None = None,
    ) -> None:
        self._frames = deque(frames)
        self._audio = deque(audio)
        self.fail_capture = fail_capture
        self.on_capture = on_capture
        self.calls = 0

    def grab_frame(self) -> SyntheticFrame:
        return self._grab(self._frames, "frame")

    def grab_audio(self) -> SyntheticAudio:
        return self._grab(self._audio, "áudio")

    def _grab(self, queue: deque[Any], label: str) -> Any:
        self.calls += 1
        if self.on_capture is not None:
            self.on_capture()
        if self.fail_capture:
            raise GlassCaptureError(f"falha simulada de captura de {label}")
        if not queue:
            raise GlassCaptureError(f"nenhum {label} sintético roteirizado")
        return queue.popleft()


class FakeGlassHUD:
    """Registra primitivas aceitas; rejeita as inválidas com erro."""

    def __init__(self, *, policy: HudPolicy | None = None) -> None:
        self.policy = policy or HudPolicy()
        self.frames: list[BaseModel] = []
        self.rejected: list[str] = []

    def show(self, payload: dict[str, Any] | BaseModel) -> BaseModel:
        try:
            primitive = validate_hud_payload(payload, policy=self.policy)
        except HudPayloadError as exc:
            self.rejected.append(str(exc))
            raise
        self.frames.append(primitive)
        return primitive

    def kinds(self) -> list[str]:
        return [str(getattr(frame, "kind")) for frame in self.frames]


@dataclass(frozen=True)
class RetainedObservation:
    """Só o derivado retido; nunca bytes brutos."""

    capture_id: str
    kind: CaptureKind
    summary: str
    captured_at: datetime
    retained_at: datetime
    via: str


class InMemoryRetentionSink:
    def __init__(self) -> None:
        self.records: list[RetainedObservation] = []

    def store(self, observation: RetainedObservation) -> None:
        self.records.append(observation)


@dataclass
class GlassMetrics:
    captures_started: int = 0
    captures_completed: int = 0
    tool_calls: int = 0
    failures: int = 0
    retained: int = 0
    discarded: int = 0
    expired: int = 0
    hud_accepted: int = 0
    hud_rejected: int = 0
    max_capture_bytes: int = 0
    max_hud_bytes: int = 0
    latencies_ms: list[float] = field(default_factory=list)


@dataclass
class _Pending:
    capture_id: str
    kind: CaptureKind
    captured_at: float
    expires_at: float
    payload_bytes: int
    views: dict[str, PerceptionContent]
    objects: tuple[str, ...]
    retained_summary: str


class FakeGlassSession:
    """Coordena estados, TTLs, retenção e métricas de uma sessão simulada."""

    def __init__(
        self,
        *,
        capture: FakeGlassCapture,
        hud: FakeGlassHUD,
        sink: InMemoryRetentionSink | None = None,
        clock: Callable[[], float] | None = None,
        arm_ttl_seconds: float = ARM_TTL_SECONDS,
        capture_ttl_seconds: float = CAPTURE_TTL_SECONDS,
    ) -> None:
        if arm_ttl_seconds <= 0 or capture_ttl_seconds <= 0:
            raise ValueError("TTLs devem ser positivos")
        self.capture_source = capture
        self.hud = hud
        self.sink = sink if sink is not None else InMemoryRetentionSink()
        self.clock = clock or FakeClock()
        self.arm_ttl_seconds = arm_ttl_seconds
        self.capture_ttl_seconds = capture_ttl_seconds
        self.metrics = GlassMetrics()
        self.state: GlassState = "idle"
        self._armed_until: float | None = None
        self._pending: _Pending | None = None
        self._raw: bytes | None = None
        self._closed: dict[str, str] = {}
        self._seq = 0

    @property
    def permissions(self) -> frozenset[str]:
        return GLASS_PERMISSIONS

    @property
    def capture_indicator(self) -> bool:
        return self.state in ("capturing", "processing")

    @property
    def raw_bytes_held(self) -> int:
        return len(self._raw) if self._raw is not None else 0

    @property
    def pending_capture_id(self) -> str | None:
        return self._pending.capture_id if self._pending is not None else None

    # --- controle do usuário ----------------------------------------------

    def arm(self) -> None:
        """Ativação explícita para **uma** captura."""

        self.tick()
        if self.state in _IN_FLIGHT:
            raise GlassStateError(f"não é possível ativar no estado {self.state}")
        self.state = "armed"
        self._armed_until = self.clock() + self.arm_ttl_seconds
        self._status()

    def stop(self) -> None:
        """Impede novas capturas e descarta o pendente. Não cancela trabalho já iniciado."""

        if self._pending is not None:
            self._close_pending("discarded")
        self._raw = None
        self._armed_until = None
        self.state = "stopped"
        self._status()

    def tick(self) -> None:
        """Aplica TTLs de ativação e de captura pendente."""

        now = self.clock()
        if self.state == "armed" and self._armed_until is not None and now >= self._armed_until:
            self._armed_until = None
            self.state = "idle"
            self._status()
        if (
            self.state == "awaiting_retention_decision"
            and self._pending is not None
            and now >= self._pending.expires_at
        ):
            self._close_pending("expired")
            self.state = "discarded"
            self._status()

    def capture_frame(self) -> str:
        return self._capture("frame")

    def capture_audio(self) -> str:
        """Push-to-talk do usuário; não é exposto como tool."""

        return self._capture("audio")

    def decide_retention(self, capture_id: str, choice: str, *, via: str) -> GlassState:
        """Decisão do usuário sobre o pendente. Único caminho para reter."""

        if via not in ("user_confirmation", "user_command"):
            raise GlassStateError(f"retenção exige decisão do usuário, não {via!r}")
        if choice not in ("retain", "discard"):
            raise GlassStateError(f"decisão inválida: {choice!r}")
        self.tick()
        if self._closed.get(capture_id) == "expired":
            raise GlassExpiredError(f"captura {capture_id} expirou e foi descartada")
        pending = self._pending
        if (
            self.state != "awaiting_retention_decision"
            or pending is None
            or pending.capture_id != capture_id
        ):
            raise GlassStateError(f"captura {capture_id} não aguarda decisão")
        if choice == "retain":
            self.sink.store(
                RetainedObservation(
                    capture_id=pending.capture_id,
                    kind=pending.kind,
                    summary=pending.retained_summary,
                    captured_at=_utc(pending.captured_at),
                    retained_at=_utc(self.clock()),
                    via=via,
                )
            )
            self._close_pending("retained")
            self.state = "retained"
        else:
            self._close_pending("discarded")
            self.state = "discarded"
        self._status()
        return self.state

    def show_hud(self, payload: dict[str, Any] | BaseModel) -> BaseModel:
        try:
            primitive = self.hud.show(payload)
        except HudPayloadError:
            self.metrics.hud_rejected += 1
            raise
        self.metrics.hud_accepted += 1
        size = hud_payload_bytes(primitive.model_dump(mode="json", exclude_none=True))
        self.metrics.max_hud_bytes = max(self.metrics.max_hud_bytes, size)
        return primitive

    # --- percepção (usada pelas tools) --------------------------------------

    def perceive(
        self,
        tool: PerceptionTool,
        capture_id: str,
        *,
        label: str | None = None,
    ) -> PerceptionResult:
        self.metrics.tool_calls += 1
        try:
            return self._perceive(tool, capture_id, label)
        except GlassError:
            self.metrics.failures += 1
            raise

    def _perceive(self, tool: str, capture_id: str, label: str | None) -> PerceptionResult:
        self.tick()
        closed = self._closed.get(capture_id)
        if closed == "expired":
            raise GlassExpiredError(f"captura {capture_id} expirou e foi descartada")
        if closed is not None:
            raise GlassStateError(f"captura {capture_id} não está mais disponível ({closed})")
        pending = self._pending
        if pending is None or pending.capture_id != capture_id:
            raise GlassStateError(f"captura desconhecida: {capture_id}")
        allowed = _FRAME_TOOLS if pending.kind == "frame" else _AUDIO_TOOLS
        if tool not in allowed:
            raise GlassStateError(f"{tool} não se aplica a captura de {pending.kind}")
        if tool == "glass_find_object":
            if not label:
                raise GlassStateError("glass_find_object exige label")
            needle = label.casefold()
            matches = [obj for obj in pending.objects if needle in obj.casefold()]
            content = _content(
                "objects", f"{len(matches)} ocorrência(s) de '{label}'", matches
            )
        else:
            content = pending.views[tool]
        result = PerceptionResult(
            source=tool,
            capture_id=pending.capture_id,
            captured_at=_utc(pending.captured_at),
            content=content,
            retention="pending_user_decision",
            payload_bytes=pending.payload_bytes,
        )
        perception_result_json(result)
        return result

    # --- internos -----------------------------------------------------------

    def _capture(self, kind: CaptureKind) -> str:
        self.tick()
        if self.state != "armed":
            raise GlassStateError(f"captura exige ativação explícita (estado: {self.state})")
        started = self.clock()
        self._armed_until = None
        self.state = "capturing"
        self.metrics.captures_started += 1
        self._status()
        self._seq += 1
        capture_id = f"cap-{self._seq:04d}"
        try:
            item = (
                self.capture_source.grab_frame()
                if kind == "frame"
                else self.capture_source.grab_audio()
            )
            if self.state == "stopped":
                raise GlassStateError("sessão parada durante a captura; resultado descartado")
            size = len(item.data)
            self.metrics.max_capture_bytes = max(self.metrics.max_capture_bytes, size)
            if size > MAX_CAPTURE_BYTES:
                raise GlassPayloadError(f"captura com {size} bytes excede {MAX_CAPTURE_BYTES}")
            self._raw = bytes(item.data)
            self.state = "processing"
            self._status()
            pending = self._process(capture_id, kind, item, size, captured_at=started)
        except GlassError:
            self._raw = None
            if self.state == "stopped":
                self.metrics.discarded += 1
                self._closed[capture_id] = "discarded"
            else:
                self._fail(capture_id)
            raise
        self._raw = None
        now = self.clock()
        self._pending = pending
        self.state = "awaiting_retention_decision"
        self.metrics.captures_completed += 1
        self.metrics.latencies_ms.append((now - started) * 1000.0)
        self._status()
        self.show_hud(
            {
                "kind": "confirmation",
                "title": "Salvar observação?",
                "options": ["yes", "no"],
                "expires_at": _utc(pending.expires_at).isoformat(),
            }
        )
        return capture_id

    def _process(
        self,
        capture_id: str,
        kind: CaptureKind,
        item: SyntheticFrame | SyntheticAudio,
        size: int,
        *,
        captured_at: float,
    ) -> _Pending:
        if item.fail_processing:
            raise GlassCaptureError("falha simulada de processamento")
        expires_at = self.clock() + self.capture_ttl_seconds
        if isinstance(item, SyntheticFrame):
            objects = tuple(item.objects)
            views = {
                "glass_capture_frame": _content(
                    "frame", f"frame sintético {item.width}x{item.height}", []
                ),
                "glass_describe_frame": _content("description", item.description, []),
                "glass_read_visible_text": _content(
                    "text",
                    f"{len(item.visible_text)} linha(s) de texto visível",
                    list(item.visible_text),
                ),
            }
            _content("objects", "objetos", list(objects))  # valida limites dos itens
            summary = item.description
        else:
            objects = ()
            views = {"glass_transcribe_audio": _content("audio", item.transcript, [])}
            summary = item.transcript
        return _Pending(
            capture_id=capture_id,
            kind=kind,
            captured_at=captured_at,
            expires_at=expires_at,
            payload_bytes=size,
            views=views,
            objects=objects,
            retained_summary=summary,
        )

    def _fail(self, capture_id: str) -> None:
        self.metrics.failures += 1
        self._closed[capture_id] = "error"
        self._pending = None
        self.state = "error"
        self._status()
        self.show_hud(
            {"kind": "error", "code": "capture_failed", "message": "Falha na captura; nada retido."}
        )

    def _close_pending(self, status: str) -> None:
        assert self._pending is not None
        self._closed[self._pending.capture_id] = status
        if status == "retained":
            self.metrics.retained += 1
        else:
            self.metrics.discarded += 1
            if status == "expired":
                self.metrics.expired += 1
        self._pending = None

    def _status(self) -> None:
        self.show_hud(
            {
                "kind": "status",
                "state": self.state,
                "capture_indicator": self.capture_indicator,
            }
        )


def _content(kind: str, summary: str, items: list[str]) -> PerceptionContent:
    try:
        return PerceptionContent(kind=kind, summary=summary, items=items)
    except ValidationError as exc:
        details = "; ".join(f"{err['loc']}: {err['msg']}" for err in exc.errors())
        raise GlassPayloadError(f"derivado fora do limite ({kind}): {details}") from exc


def _utc(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
