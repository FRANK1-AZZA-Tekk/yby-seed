"""HTML mínimo do painel — todo campo dinâmico passa por html.escape."""

from __future__ import annotations

import html
from datetime import datetime, timezone

from src.painel.models import PainelItem, PainelResumo

_CSS = """
body { font-family: system-ui, sans-serif; margin: 1.5rem; background: #0f1419; color: #e7ecf1; }
h1 { font-size: 1.4rem; }
h2 { font-size: 1.1rem; margin-top: 1.5rem; border-bottom: 1px solid #334; padding-bottom: 0.3rem; }
.card { background: #1a2332; border-radius: 8px; padding: 0.75rem 1rem; margin: 0.5rem 0; }
.meta { color: #9aa7b5; font-size: 0.85rem; }
.state-proposto { color: #7ec8ff; }
.state-executado { color: #7ddea3; }
.state-falhou { color: #ff8a8a; }
.state-aguardando_aprovacao { color: #ffd27d; }
.health { font-weight: 600; }
ul { list-style: none; padding: 0; }
"""


def _iso(ts: float) -> str:
    if not ts:
        return "—"
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return "—"


def _item_li(item: PainelItem) -> str:
    state_class = f"state-{html.escape(item.state, quote=True)}"
    return (
        f'<li class="card">'
        f'<div><strong>{html.escape(item.title)}</strong> '
        f'<span class="{state_class}">[{html.escape(item.state)}]</span></div>'
        f'<div class="meta">{html.escape(item.origin)} · {_iso(item.timestamp)}</div>'
        f'<div>{html.escape(item.detail)}</div>'
        f"</li>"
    )


def _section(title: str, items: list[PainelItem]) -> str:
    if not items:
        body = '<p class="meta">(vazio)</p>'
    else:
        body = "<ul>" + "".join(_item_li(i) for i in items) + "</ul>"
    return f"<h2>{html.escape(title)}</h2>{body}"


def render_resumo(resumo: PainelResumo) -> str:
    ollama_esc = html.escape(resumo.ollama)
    parts = [
        "<!DOCTYPE html>",
        '<html lang="pt-BR"><head><meta charset="utf-8">',
        "<title>YBY Painel</title>",
        f"<style>{_CSS}</style>",
        "</head><body>",
        "<h1>YBY Painel (somente leitura)</h1>",
        f'<div class="card health">Saúde Ollama: {ollama_esc}</div>',
        _section("Rotinas recentes", resumo.routines),
        _section("Alertas ativos", resumo.alerts),
        _section("Lembretes", resumo.reminders),
        _section("Camadas develop", resumo.develop_layers),
        "</body></html>",
    ]
    return "\n".join(parts)
