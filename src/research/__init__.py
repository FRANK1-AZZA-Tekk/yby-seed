"""Pesquisa consentida com HTTP fake (sem busca real)."""

from src.research.consent import ResearchError, require_consent, resolve_consent
from src.research.fake_http import FakeHttpClient, FakeResponse
from src.research.search import SearchHit, SearchReport, format_report, search

__all__ = [
    "FakeHttpClient",
    "FakeResponse",
    "ResearchError",
    "SearchHit",
    "SearchReport",
    "format_report",
    "require_consent",
    "resolve_consent",
    "search",
]
