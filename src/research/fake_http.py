"""Cliente HTTP fake: respostas determinísticas, zero rede."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class FakeResponse:
    status_code: int
    text: str

    def json(self) -> object:
        return json.loads(self.text)


class FakeHttpClient:
    """Simula GET de busca. Não usa requests/urllib de rede."""

    def get(self, url: str, *, timeout: float = 5.0) -> FakeResponse:
        del timeout  # API compat; sem I/O
        parsed = urlparse(url)
        query = ""
        if parsed.query:
            params = parse_qs(parsed.query)
            values = params.get("q") or params.get("query") or [""]
            query = values[0]
        hits = _synthetic_hits(query)
        payload = {
            "transport": "fake",
            "query": query,
            "results": hits,
            "warning": "HTTP fake — sem busca real na rede",
        }
        return FakeResponse(
            status_code=200,
            text=json.dumps(payload, ensure_ascii=False),
        )


def _synthetic_hits(query: str) -> list[dict[str, str]]:
    seed = query.strip() or "vazio"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
    slug = "-".join(seed.casefold().split())[:48] or "consulta"
    return [
        {
            "title": f"Fake result 1: {seed}",
            "url": f"https://fake.yby.local/r/{slug}-{digest}-1",
            "snippet": f"Trecho sintético sobre “{seed}” (hit 1, id {digest}).",
        },
        {
            "title": f"Fake result 2: {seed}",
            "url": f"https://fake.yby.local/r/{slug}-{digest}-2",
            "snippet": f"Segundo hit determinístico para “{seed}”.",
        },
        {
            "title": f"Fake result 3: {seed}",
            "url": f"https://fake.yby.local/r/{slug}-{digest}-3",
            "snippet": "Terceiro hit — transporte fake; não é a web real.",
        },
    ]
