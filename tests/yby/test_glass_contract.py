"""Contrato YBY Glass G0: primitivas do HUD, resultado de percepção e argumentos (offline)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.yby.glass.contracts import (
    HUD_KINDS,
    MAX_HUD_BYTES,
    MAX_RESULT_BYTES,
    CaptureFrameArgs,
    CaptureRefArgs,
    FindObjectArgs,
    GlassPayloadError,
    HudPayloadError,
    HudPolicy,
    PerceptionContent,
    PerceptionResult,
    hud_payload_bytes,
    perception_result_json,
    validate_hud_payload,
)

EXPIRES = "2026-11-26T12:00:30+00:00"

VALID_PRIMITIVES = [
    {"kind": "text", "text": "Mesa à frente"},
    {"kind": "title", "text": "YBY Glass"},
    {"kind": "list", "items": ["um", "dois", "três"]},
    {"kind": "status", "state": "capturing", "capture_indicator": True},
    {"kind": "confirmation", "title": "Salvar observação?", "options": ["yes", "no"], "expires_at": EXPIRES},
    {"kind": "marker", "x": 0.5, "y": 0.25, "label": "chave"},
    {"kind": "progress", "value": 40, "label": "processando"},
    {"kind": "error", "code": "capture_failed", "message": "Falha na captura."},
]


def _result(**overrides: object) -> PerceptionResult:
    data: dict[str, object] = {
        "source": "glass_capture_frame",
        "capture_id": "cap-0001",
        "captured_at": datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc),
        "content": {"kind": "frame", "summary": "frame sintético"},
        "retention": "pending_user_decision",
        "payload_bytes": 1024,
    }
    data.update(overrides)
    return PerceptionResult.model_validate(data)


# --- HUD ---------------------------------------------------------------------


def test_every_minimum_hud_kind_is_covered_and_accepted():
    assert {p["kind"] for p in VALID_PRIMITIVES} == HUD_KINDS
    for payload in VALID_PRIMITIVES:
        primitive = validate_hud_payload(payload)
        assert primitive.kind == payload["kind"]
        assert hud_payload_bytes(payload) <= MAX_HUD_BYTES


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "html", "text": "x"},
        {"kind": "command", "text": "rm -rf /"},
        {"kind": "text"},
        {"kind": "text", "text": ""},
        {"kind": "text", "text": "ok", "onclick": "x"},
        {"kind": "text", "text": "<b>negrito</b>"},
        {"kind": "text", "text": "<script>alert(1)</script>"},
        {"kind": "title", "text": "veja https://exemplo.com"},
        {"kind": "text", "text": "veja www.exemplo.com"},
        {"kind": "text", "text": "linha1\nlinha2"},
        {"kind": "text", "text": "a" * 121},
        {"kind": "list", "items": []},
        {"kind": "list", "items": ["1", "2", "3", "4", "5", "6"]},
        {"kind": "status", "state": "capturing", "capture_indicator": False},
        {"kind": "status", "state": "recording", "capture_indicator": True},
        {"kind": "confirmation", "title": "Salvar?", "options": ["yes"], "expires_at": EXPIRES},
        {"kind": "confirmation", "title": "Salvar?", "options": ["yes", "yes"], "expires_at": EXPIRES},
        {"kind": "confirmation", "title": "Salvar?", "options": ["yes", "maybe"], "expires_at": EXPIRES},
        {"kind": "confirmation", "title": "Salvar?", "options": ["yes", "no"]},
        {"kind": "confirmation", "title": "Salvar?", "options": ["yes", "no"], "expires_at": "2026-11-26T12:00:30"},
        {"kind": "marker", "x": 1.5, "y": 0.5},
        {"kind": "progress", "value": 101},
        {"kind": "error", "code": "Falha!", "message": "x"},
    ],
)
def test_invalid_hud_primitives_are_rejected(payload):
    with pytest.raises(HudPayloadError):
        validate_hud_payload(payload)


def test_hud_rejects_non_object_payload():
    with pytest.raises(HudPayloadError):
        validate_hud_payload(["text", "oi"])  # type: ignore[arg-type]


def test_hud_byte_limit_is_enforced_even_within_char_limits():
    payload = {"kind": "list", "items": ["😀" * 40] * 5}
    assert hud_payload_bytes(payload) > MAX_HUD_BYTES
    with pytest.raises(HudPayloadError, match="excede"):
        validate_hud_payload(payload)


def test_private_content_requires_explicit_display_policy():
    payload = {"kind": "text", "text": "saldo da conta", "sensitivity": "private"}
    with pytest.raises(HudPayloadError, match="private"):
        validate_hud_payload(payload)
    primitive = validate_hud_payload(payload, policy=HudPolicy(allow_private_display=True))
    assert primitive.sensitivity == "private"


def test_confirmation_matches_spec_example():
    primitive = validate_hud_payload(
        {
            "kind": "confirmation",
            "title": "Salvar observação?",
            "options": ["yes", "no"],
            "expires_at": EXPIRES,
        }
    )
    assert primitive.options == ["yes", "no"]
    assert primitive.expires_at.tzinfo is not None


# --- Percepção ---------------------------------------------------------------


def test_perception_result_is_structured_and_untrusted():
    payload = perception_result_json(_result())
    assert set(payload) == {
        "source",
        "capture_id",
        "captured_at",
        "content",
        "trust",
        "retention",
        "payload_bytes",
    }
    assert payload["trust"] == "untrusted"
    assert payload["retention"] == "pending_user_decision"
    json.dumps(payload)


def test_perception_result_rejects_trusted_extra_and_unknown_source():
    with pytest.raises(ValidationError):
        _result(trust="trusted")
    with pytest.raises(ValidationError):
        _result(raw_image="AAAA")
    with pytest.raises(ValidationError):
        _result(source="glass_run_command")
    with pytest.raises(ValidationError):
        _result(capture_id="../etc/passwd")
    with pytest.raises(ValidationError):
        _result(captured_at=datetime(2026, 11, 26, 12, 0))


def test_perception_content_limits():
    with pytest.raises(ValidationError):
        PerceptionContent(kind="frame", summary="x" * 281)
    with pytest.raises(ValidationError):
        PerceptionContent(kind="text", summary="ok", items=["a"] * 9)
    with pytest.raises(ValidationError):
        PerceptionContent(kind="text", summary="ok", items=["a" * 61])
    with pytest.raises(ValidationError):
        PerceptionContent(kind="frame", summary="ok", raw=b"\x00")


def test_perception_result_byte_cap_raises_instead_of_truncating():
    content = {"kind": "text", "summary": "😀" * 280, "items": ["😀" * 60] * 8}
    result = _result(content=content)
    with pytest.raises(GlassPayloadError, match=str(MAX_RESULT_BYTES)):
        perception_result_json(result)


def test_tool_args_are_strict():
    CaptureFrameArgs.model_validate({})
    with pytest.raises(ValidationError):
        CaptureFrameArgs.model_validate({"continuous": True})
    with pytest.raises(ValidationError):
        CaptureRefArgs.model_validate({"capture_id": "frame-1"})
    with pytest.raises(ValidationError):
        FindObjectArgs.model_validate({"capture_id": "cap-0001", "label": "x" * 41})
    with pytest.raises(ValidationError):
        FindObjectArgs.model_validate({"capture_id": "cap-0001", "label": "<script>"})
