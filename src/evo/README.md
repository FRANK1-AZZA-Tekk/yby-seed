# Evo v0.1 — local observability (reports only)

Honest scope: **collect → sanitize → SQLite(+FTS5) → day aggregate → local Ollama (or heuristic) → Markdown report.**

Aligned with Ring 1 of `docs/future/EVO_NIGHT_WATCH.md` (design may live on another branch). **Not** in v0.1: sandbox apply, auto code changes, Night Watch promotion, FinOps cloud registry writes, any outbound cloud calls from Evo.

## Layout

| Path | Role |
|---|---|
| `src/evo/` | Module (this package) |
| `$XDG_DATA_HOME/yby/evo/evo.sqlite3` | Local store (default; outside git) |
| `evo/reports/` | Generated Markdown (`*.md` gitignored; `EXAMPLE.md` kept) |
| `logs/cloud_usage.jsonl` | Optional **read-only** event source if present |

Overrides: `YBY_EVO_DB`, `YBY_EVO_REPORTS`, `YBY_EVO_MODEL`, `YBY_EVO_NO_OLLAMA=1`.

Cycle states recorded (v0.1): `observing` → `analyzing` → `completed`.

## CLI

```bash
python yby.py evo ingest --seed-demo --day 2026-11-18
python yby.py evo report --day 2026-11-18 --no-ollama --stdout
python -m src.evo report --day 2026-11-18 --seed-demo --no-ollama
python yby.py evo search "ollama" --day 2026-11-18
```

Analysis uses `OllamaProvider` (local only). Tests mock the completer; `--no-ollama` forces heuristics.

## Future

v0.2+ may add proposals/sandbox/approval per Night Watch design. This package stays a reporting surface until then.
