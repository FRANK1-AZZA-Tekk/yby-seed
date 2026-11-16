"""Preferências no vault com consentimento explícito (lote 20). Sem Vector DB."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from src.engine.secret_gate import find_secret, redact_for_cloud
from src.memory.vault import Vault

PREFS_FILENAME = "prefs.json"
MAX_VALUE_LEN = 200

ALLOWED_KEYS = frozenset(
    {
        "locale",
        "reply_style",
        "share_notes_with_cloud",
        "remember_failures",
        "allow_web_search",
    }
)
CONSENT_REQUIRED = frozenset(
    {"share_notes_with_cloud", "remember_failures", "allow_web_search"}
)
REPLY_STYLES = frozenset({"short", "teach"})


class PrefsError(ValueError):
    """Preferência inválida ou sem consentimento."""


@dataclass(frozen=True)
class PreferenceRecord:
    key: str
    value: str
    updated_at: str
    consent_at: str | None = None


def prefs_path(vault: Vault) -> Path:
    return vault.root / ".yby" / PREFS_FILENAME


def load_prefs(vault: Vault) -> dict[str, PreferenceRecord]:
    path = prefs_path(vault)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PrefsError(f"prefs.json inválido: {exc}") from exc
    if not isinstance(data, dict):
        raise PrefsError("prefs.json deve ser um objeto")
    items = data.get("preferences", data)
    if not isinstance(items, dict):
        raise PrefsError("preferences deve ser um objeto")
    out: dict[str, PreferenceRecord] = {}
    for key, raw in items.items():
        if not isinstance(key, str) or not isinstance(raw, dict):
            continue
        value = raw.get("value")
        updated = raw.get("updated_at")
        if not isinstance(value, str) or not isinstance(updated, str):
            continue
        consent = raw.get("consent_at")
        if consent is not None and not isinstance(consent, str):
            consent = None
        out[key] = PreferenceRecord(
            key=key,
            value=value,
            updated_at=updated,
            consent_at=consent,
        )
    return out


def list_prefs(vault: Vault) -> list[PreferenceRecord]:
    return sorted(load_prefs(vault).values(), key=lambda item: item.key)


def get_pref(vault: Vault, key: str) -> PreferenceRecord:
    normalized = key.strip()
    if normalized not in ALLOWED_KEYS:
        raise PrefsError(_unknown_key(normalized))
    prefs = load_prefs(vault)
    if normalized not in prefs:
        raise PrefsError(f"preferência não definida: {normalized}")
    return prefs[normalized]


def set_pref(
    vault: Vault,
    key: str,
    value: str,
    *,
    consent: bool = False,
    now: float | None = None,
) -> PreferenceRecord:
    normalized = key.strip()
    if normalized not in ALLOWED_KEYS:
        raise PrefsError(_unknown_key(normalized))

    raw = value.strip()
    if not raw:
        raise PrefsError("valor vazio")
    if len(raw) > MAX_VALUE_LEN:
        raise PrefsError(f"valor longo demais (máx {MAX_VALUE_LEN} chars)")
    hit = find_secret(raw)
    if hit is not None:
        raise PrefsError(f"valor bloqueado: parece conter segredo ({hit.kind})")
    cleaned = redact_for_cloud(raw)

    if normalized == "reply_style" and cleaned not in REPLY_STYLES:
        raise PrefsError(
            f"reply_style inválido: {cleaned!r}. Use um de: {', '.join(sorted(REPLY_STYLES))}."
        )
    if normalized in CONSENT_REQUIRED:
        if cleaned not in {"0", "1", "true", "false", "yes", "no", "on", "off"}:
            raise PrefsError(
                f"{normalized} deve ser booleano textual (0/1, true/false, yes/no, on/off)"
            )
        cleaned = "1" if cleaned.casefold() in {"1", "true", "yes", "on"} else "0"

    needs_consent = normalized in CONSENT_REQUIRED
    if needs_consent and not consent:
        raise PrefsError(
            f"chave {normalized} exige consentimento explícito (--consent). "
            "Sem isso a preferência não é gravada."
        )

    ts = now if now is not None else time.time()
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
    existing = load_prefs(vault)
    consent_at = stamp if needs_consent else None
    if needs_consent and normalized in existing and existing[normalized].consent_at:
        # novo set com consent renova o timestamp
        consent_at = stamp

    record = PreferenceRecord(
        key=normalized,
        value=cleaned,
        updated_at=stamp,
        consent_at=consent_at,
    )
    existing[normalized] = record
    _save(vault, existing)
    return record


def format_record(record: PreferenceRecord) -> str:
    consent = f" consent_at={record.consent_at}" if record.consent_at else ""
    return f"{record.key}={record.value} updated_at={record.updated_at}{consent}"


def _save(vault: Vault, prefs: dict[str, PreferenceRecord]) -> None:
    path = prefs_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "yby-prefs/v1",
        "preferences": {
            key: {
                "value": rec.value,
                "updated_at": rec.updated_at,
                **({"consent_at": rec.consent_at} if rec.consent_at else {}),
            }
            for key, rec in sorted(prefs.items())
        },
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=".prefs-",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _unknown_key(key: str) -> str:
    allowed = ", ".join(sorted(ALLOWED_KEYS))
    return f"chave desconhecida: {key!r}. Use uma de: {allowed}."
