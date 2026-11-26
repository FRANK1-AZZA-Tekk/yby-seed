"""YBY Glass G0: contrato simulado de captura discreta, percepção e HUD. Ver docs/YBY_GLASS_SPEC.md."""

from __future__ import annotations

from src.yby.glass.contracts import (
    GLASS_PERMISSIONS,
    GlassCaptureError,
    GlassError,
    GlassExpiredError,
    GlassPayloadError,
    GlassState,
    GlassStateError,
    HudPayloadError,
    HudPolicy,
    PerceptionResult,
    validate_hud_payload,
)
from src.yby.glass.simulator import (
    FakeClock,
    FakeGlassCapture,
    FakeGlassHUD,
    FakeGlassSession,
    GlassMetrics,
    InMemoryRetentionSink,
    RetainedObservation,
    SyntheticAudio,
    SyntheticFrame,
)

__all__ = [
    "GLASS_PERMISSIONS",
    "FakeClock",
    "FakeGlassCapture",
    "FakeGlassHUD",
    "FakeGlassSession",
    "GlassCaptureError",
    "GlassError",
    "GlassExpiredError",
    "GlassMetrics",
    "GlassPayloadError",
    "GlassState",
    "GlassStateError",
    "HudPayloadError",
    "HudPolicy",
    "InMemoryRetentionSink",
    "PerceptionResult",
    "RetainedObservation",
    "SyntheticAudio",
    "SyntheticFrame",
    "validate_hud_payload",
]
