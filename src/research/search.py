"""Pesquisa consentida com transporte fake (lote 21)."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from src.engine.secret_gate import find_secret, redact_for_cloud
from src.memory.vault import Vault
from src.research.consent import ResearchError, require_consent, resolve_consent
from src.research.fake_http import FakeHttpClient


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class SearchReport:
    query: str
    hits: tuple[SearchHit, ...]
    transport: str
    warning: str


def search(
    query: str,
    *,
    consented: bool = False,
    client: FakeHttpClient | None = None,
    vault: Vault | None = None,
) -> SearchReport:
    """Executa busca fake após gate de consentimento. Sem rede real."""

    raw = query.strip()
    if not raw:
        raise ResearchError("consulta vazia")
    secret = find_secret(raw)
    if secret is not None:
        raise ResearchError(
            f"consulta bloqueada: parece conter segredo ({secret.kind})"
        )
    cleaned = redact_for_cloud(raw)

    allowed = resolve_consent(flag_consent=consented, vault=vault)
    require_consent(consented=allowed)

    http = client or FakeHttpClient()
    url = f"https://fake.yby.local/search?q={quote(cleaned)}"
    response = http.get(url)
    if response.status_code != 200:
        raise ResearchError(f"fake HTTP status {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ResearchError("resposta fake inválida")
    rows = payload.get("results") or []
    hits: list[SearchHit] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "")
            url_hit = str(row.get("url") or "")
            snippet = str(row.get("snippet") or "")
            if title and url_hit:
                hits.append(SearchHit(title=title, url=url_hit, snippet=snippet))
    warning = str(payload.get("warning") or "HTTP fake — sem busca real na rede")
    return SearchReport(
        query=cleaned,
        hits=tuple(hits),
        transport="fake",
        warning=warning,
    )


def format_report(report: SearchReport) -> str:
    lines = [
        f"query: {report.query}",
        f"transport: {report.transport}",
        f"aviso: {report.warning}",
        f"hits: {len(report.hits)}",
    ]
    for index, item in enumerate(report.hits, start=1):
        lines.append(f"  [{index}] {item.title}")
        lines.append(f"      {item.url}")
        if item.snippet:
            lines.append(f"      {item.snippet}")
    return "\n".join(lines)
