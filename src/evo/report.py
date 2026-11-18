"""Gerador de relatório Markdown (v0.1 — só lê/escreve local)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.evo.aggregate import DayAggregate
from src.evo.analyze import AnalysisResult
from src.evo.paths import resolve_reports_dir
from src.evo.sanitize import sanitize_text


def render_markdown(
    agg: DayAggregate,
    analysis: AnalysisResult,
    *,
    generated_at: str | None = None,
) -> str:
    """Monta o relatório com as secções de aceitação."""

    when = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines: list[str] = [
        f"# Evo report — {agg.day}",
        "",
        f"_Generated at {when} (local Evo v0.1). Offline. No automatic code changes._",
        "",
        "## Day summary",
        "",
        f"- **Day:** {agg.day}",
        f"- **Events:** {agg.total}",
        f"- **By kind:** {_fmt_counts(agg.by_kind)}",
        f"- **By severity:** {_fmt_counts(agg.by_severity)}",
        f"- **Sources:** {_fmt_counts(agg.sources) or '(none)'}",
        "- **Analyzer:** "
        + (
            f"Ollama `{analysis.used_model}`"
            if analysis.used_model and not analysis.offline_fallback
            else "heuristic fallback (local)"
        ),
        "",
        "## Problems",
        "",
    ]
    if agg.problems:
        for item in agg.problems:
            lines.append(f"- {sanitize_text(item)}")
    else:
        lines.append("- (none recorded)")

    lines.extend(["", "## Evidence", ""])
    if agg.evidence:
        for item in agg.evidence:
            lines.append(f"- {sanitize_text(item)}")
    else:
        lines.append("- (no events)")

    lines.extend(["", "## Hypotheses", ""])
    if analysis.hypotheses:
        for hyp in analysis.hypotheses:
            title = sanitize_text(str(hyp.get("title") or "hypothesis"))
            rationale = sanitize_text(str(hyp.get("rationale") or ""))
            conf = hyp.get("confidence")
            conf_s = f" (confidence {conf})" if conf is not None else ""
            lines.append(f"- **{title}**{conf_s}: {rationale}")
    else:
        lines.append("- (none)")

    lines.extend(["", "## Prioritized proposals", ""])
    if analysis.proposals:
        for prop in analysis.proposals:
            title = sanitize_text(str(prop.get("title") or "proposal"))
            rationale = sanitize_text(str(prop.get("rationale") or ""))
            prio = prop.get("priority", "?")
            lines.append(f"1. **P{prio} — {title}**: {rationale}")
    else:
        lines.append("- (none)")

    lines.extend(["", "## Risks", ""])
    risks = list(analysis.risks) or ["Evo v0.1 reports only; human review required."]
    for risk in risks:
        lines.append(f"- {sanitize_text(str(risk))}")

    lines.extend(["", "## Next steps", ""])
    steps = list(analysis.next_steps) or ["Review this report; do not auto-apply changes."]
    for step in steps:
        lines.append(f"- {sanitize_text(str(step))}")

    lines.extend(
        [
            "",
            "---",
            "",
            "Evo v0.1 does **not** apply patches, promote Night Watch, or call cloud APIs.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(
    markdown: str,
    day: str,
    *,
    reports_dir: Path | None = None,
) -> Path:
    """Escreve `evo/reports/evo-YYYY-MM-DD.md` (cria pasta)."""

    out_dir = reports_dir or resolve_reports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"evo-{day}.md"
    path.write_text(sanitize_text(markdown), encoding="utf-8")
    return path


def _fmt_counts(counts: dict[str, int]) -> str:
    if not counts:
        return ""
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
