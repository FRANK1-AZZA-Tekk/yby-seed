"""Contratos Pydantic do YBY Glass G0 (percepção e HUD). Sem I/O."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)

GlassState = Literal[
    "idle",
    "armed",
    "capturing",
    "processing",
    "awaiting_retention_decision",
    "retained",
    "discarded",
    "stopped",
    "error",
]

PerceptionTool = Literal[
    "glass_capture_frame",
    "glass_transcribe_audio",
    "glass_describe_frame",
    "glass_read_visible_text",
    "glass_find_object",
]

RetentionStatus = Literal["pending_user_decision", "retained", "discarded"]
RetentionChoice = Literal["retain", "discard"]
RetentionVia = Literal["user_confirmation", "user_command"]

GLASS_PERMISSIONS: frozenset[str] = frozenset({"glass.perceive"})

ARM_TTL_SECONDS = 60.0
CAPTURE_TTL_SECONDS = 30.0
MAX_CAPTURE_BYTES = 262_144
MAX_SUMMARY_CHARS = 280
MAX_ITEMS = 8
MAX_ITEM_CHARS = 60
MAX_RESULT_BYTES = 2048
MAX_HUD_BYTES = 512

CAPTURE_ID_PATTERN = r"^cap-[0-9]{4,}$"

_HTML = re.compile(r"<\s*[A-Za-z!/?]")
_URL = re.compile(r"(?i)\b(?:https?://|www\.)")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class GlassError(RuntimeError):
    """Base dos erros do YBY Glass."""


class GlassStateError(GlassError):
    """Operação inválida no estado atual da sessão."""


class GlassExpiredError(GlassError):
    """Ativação ou captura pendente expirou."""


class GlassPayloadError(GlassError):
    """Payload acima do limite do contrato."""


class GlassCaptureError(GlassError):
    """Falha de captura ou de processamento."""


class HudPayloadError(GlassError):
    """Primitiva de HUD rejeitada."""


def _safe_text(value: str) -> str:
    if _CONTROL.search(value):
        raise ValueError("caractere de controle não permitido")
    if _HTML.search(value):
        raise ValueError("HTML/marcação não permitido")
    if _URL.search(value):
        raise ValueError("URL não permitida no HUD")
    return value


def _text(max_length: int, *, min_length: int = 1) -> Any:
    return Annotated[
        str,
        Field(min_length=min_length, max_length=max_length),
        AfterValidator(_safe_text),
    ]


_Text24 = _text(24)
_Text40 = _text(40)
_Text60 = _text(60)
_Text120 = _text(120)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- Percepção -------------------------------------------------------------


class PerceptionContent(_Strict):
    kind: Literal["frame", "audio", "description", "text", "objects"]
    summary: str = Field(min_length=1, max_length=MAX_SUMMARY_CHARS)
    items: list[Annotated[str, Field(min_length=1, max_length=MAX_ITEM_CHARS)]] = Field(
        default_factory=list, max_length=MAX_ITEMS
    )


class PerceptionResult(_Strict):
    """Saída de uma tool Glass para o planner. Nunca contém bytes brutos."""

    source: PerceptionTool
    capture_id: str = Field(pattern=CAPTURE_ID_PATTERN)
    captured_at: AwareDatetime
    content: PerceptionContent
    trust: Literal["untrusted"] = "untrusted"
    retention: RetentionStatus
    payload_bytes: int = Field(ge=0, le=MAX_CAPTURE_BYTES)


def perception_result_json(result: PerceptionResult) -> dict[str, Any]:
    """Serializa o resultado e aplica o teto em bytes (erro, nunca corte)."""

    payload = result.model_dump(mode="json")
    size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    if size > MAX_RESULT_BYTES:
        raise GlassPayloadError(
            f"resultado de {result.source} com {size} bytes excede {MAX_RESULT_BYTES}"
        )
    return payload


class CaptureFrameArgs(_Strict):
    """`glass_capture_frame` não aceita argumentos."""


class CaptureRefArgs(_Strict):
    capture_id: str = Field(pattern=CAPTURE_ID_PATTERN)


class FindObjectArgs(_Strict):
    capture_id: str = Field(pattern=CAPTURE_ID_PATTERN)
    label: _Text40


# --- HUD -------------------------------------------------------------------

Sensitivity = Literal["public", "private"]
ConfirmOption = Literal["yes", "no", "cancel"]


class HudText(_Strict):
    kind: Literal["text"]
    text: _Text120
    sensitivity: Sensitivity = "public"


class HudTitle(_Strict):
    kind: Literal["title"]
    text: _Text40
    sensitivity: Sensitivity = "public"


class HudList(_Strict):
    kind: Literal["list"]
    items: list[_Text40] = Field(min_length=1, max_length=5)
    sensitivity: Sensitivity = "public"


class HudStatus(_Strict):
    kind: Literal["status"]
    state: GlassState
    capture_indicator: bool
    label: _Text40 | None = None
    sensitivity: Sensitivity = "public"

    @model_validator(mode="after")
    def _indicator_when_capturing(self) -> HudStatus:
        if self.state == "capturing" and not self.capture_indicator:
            raise ValueError("status capturing exige capture_indicator=true")
        return self


class HudConfirmation(_Strict):
    kind: Literal["confirmation"]
    title: _Text60
    options: list[ConfirmOption] = Field(min_length=2, max_length=3)
    expires_at: AwareDatetime
    sensitivity: Sensitivity = "public"

    @model_validator(mode="after")
    def _unique_options(self) -> HudConfirmation:
        if len(set(self.options)) != len(self.options):
            raise ValueError("opções de confirmação repetidas")
        return self


class HudMarker(_Strict):
    kind: Literal["marker"]
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    label: _Text24 | None = None
    sensitivity: Sensitivity = "public"


class HudProgress(_Strict):
    kind: Literal["progress"]
    value: int = Field(ge=0, le=100)
    label: _Text40 | None = None
    sensitivity: Sensitivity = "public"


class HudError(_Strict):
    kind: Literal["error"]
    code: str = Field(pattern=r"^[a-z_]{1,32}$")
    message: _Text120
    sensitivity: Sensitivity = "public"


HudPrimitive = Annotated[
    HudText
    | HudTitle
    | HudList
    | HudStatus
    | HudConfirmation
    | HudMarker
    | HudProgress
    | HudError,
    Field(discriminator="kind"),
]

HUD_KINDS: frozenset[str] = frozenset(
    {"text", "title", "list", "status", "confirmation", "marker", "progress", "error"}
)

_HUD_ADAPTER: TypeAdapter[Any] = TypeAdapter(HudPrimitive)


class HudPolicy(_Strict):
    allow_private_display: bool = False


def hud_payload_bytes(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def validate_hud_payload(
    payload: dict[str, Any] | BaseModel,
    *,
    policy: HudPolicy | None = None,
) -> BaseModel:
    """Valida uma primitiva do HUD. Qualquer violação levanta `HudPayloadError`."""

    active = policy or HudPolicy()
    if isinstance(payload, BaseModel):
        raw = payload.model_dump(mode="json", exclude_none=True)
    elif isinstance(payload, dict):
        raw = payload
    else:
        raise HudPayloadError("primitiva deve ser objeto JSON")
    try:
        size = hud_payload_bytes(raw)
    except (TypeError, ValueError) as exc:
        raise HudPayloadError(f"primitiva não serializável: {exc}") from exc
    if size > MAX_HUD_BYTES:
        raise HudPayloadError(f"primitiva com {size} bytes excede {MAX_HUD_BYTES}")
    try:
        primitive = _HUD_ADAPTER.validate_python(raw)
    except ValidationError as exc:
        details = "; ".join(f"{err['loc']}: {err['msg']}" for err in exc.errors())
        raise HudPayloadError(details) from exc
    if primitive.sensitivity == "private" and not active.allow_private_display:
        raise HudPayloadError("conteúdo private exige política explícita de exibição")
    return primitive
