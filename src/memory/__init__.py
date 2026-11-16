"""Notas do vault, busca local e preferências com consentimento."""

from src.memory.prefs import (
    ALLOWED_KEYS,
    CONSENT_REQUIRED,
    PreferenceRecord,
    PrefsError,
    format_record,
    get_pref,
    list_prefs,
    load_prefs,
    set_pref,
)
from src.memory.vault import Hit, Vault, VaultError, vault_from_env

__all__ = [
    "ALLOWED_KEYS",
    "CONSENT_REQUIRED",
    "Hit",
    "PreferenceRecord",
    "PrefsError",
    "Vault",
    "VaultError",
    "format_record",
    "get_pref",
    "list_prefs",
    "load_prefs",
    "set_pref",
    "vault_from_env",
]
