"""Gate de consentimento para pesquisa (lote 21)."""

from __future__ import annotations

from src.memory.prefs import get_pref, load_prefs
from src.memory.vault import Vault, VaultError


class ResearchError(ValueError):
    """Pesquisa bloqueada ou inválida."""


def require_consent(*, consented: bool) -> None:
    """Fail-closed sem consentimento one-shot."""

    if not consented:
        raise ResearchError(
            "pesquisa exige consentimento: passe --consent "
            "ou grave allow_web_search=1 com yby prefs set … --consent"
        )


def resolve_consent(
    *,
    flag_consent: bool,
    vault: Vault | None = None,
) -> bool:
    """True se --consent ou pref allow_web_search=1 com consent_at."""

    if flag_consent:
        return True
    if vault is None:
        return False
    try:
        prefs = load_prefs(vault)
    except (VaultError, ValueError):
        return False
    record = prefs.get("allow_web_search")
    if record is None:
        return False
    return record.value == "1" and bool(record.consent_at)


def pref_allows_web_search(vault: Vault) -> bool:
    """Consulta direta da pref (testes / CLI)."""

    try:
        record = get_pref(vault, "allow_web_search")
    except Exception:
        return False
    return record.value == "1" and bool(record.consent_at)
